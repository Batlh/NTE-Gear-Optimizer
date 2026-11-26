import {readFileSync,readdirSync} from 'node:fs';
import {resolve,dirname,join,relative} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
function files(root){
 const result=[];
 for(const entry of readdirSync(root,{withFileTypes:true})){
  const p=join(root,entry.name);
  if(/(_REV_|_INTERMEDIATE_|__pycache__)/.test(entry.name))continue;
  if(entry.isDirectory())result.push(...files(p));else result.push(p);
 }
 return result;
}
const runtime=files(process.argv[2]).find(p=>p.endsWith('pyodide.mjs'));
if(!runtime)throw Error('pyodide.mjs not found');
const {loadPyodide}=await import(pathToFileURL(resolve(runtime)).href);
const py=await loadPyodide({indexURL:dirname(resolve(runtime))});
const version=process.argv[3];
if(py.version!==version)throw Error(`runtime version mismatch ${py.version}`);
const hashes={};
for(const path of [...files('src'),...files('tests')]){
 if(!/\.(py|json|tsv)$/.test(path))continue;
 const target='/work/'+relative('.',path).replaceAll('\\','/');
 py.FS.mkdirTree(dirname(target));
 const bytes=readFileSync(path);py.FS.writeFile(target,bytes);
 hashes[relative('.',path).replaceAll('\\','/')]=createHash('sha256').update(bytes).digest('hex');
}
const raw=py.runPython(`
import sys,json
sys.path[:0]=['/work/src','/work/tests']
from parity_suite import run
data=run()
json.dumps(data,ensure_ascii=False,sort_keys=True)
`);
const data=JSON.parse(raw);
if(!process.argv[4])throw Error('Native result path is required for parity');
const native=JSON.parse(readFileSync(process.argv[4],'utf8'));
// Recursive, key-sorted comparison includes every output, null, provenance and diagnostic.
function canonical(v){
 if(Array.isArray(v))return v.map(canonical);
 if(v!==null && typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])]));
 return v;
}
if(JSON.stringify(canonical(data))!==JSON.stringify(canonical(native)))throw Error('CPython/Pyodide semantic mismatch');
console.log(JSON.stringify({pyodide:py.version,python:py.runPython('sys.version'),parity:'PASS',
 core_cases:Object.keys(data.core_cases).length,opb10_vectors:data.opb10_vectors.length,
 mutations:data.mutations,source_hashes:hashes,results:data}));
