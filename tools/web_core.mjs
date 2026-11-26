import {readFileSync,readdirSync} from 'node:fs';
import {resolve,dirname,join} from 'node:path';
import {pathToFileURL} from 'node:url';
function find(root){
 for(const entry of readdirSync(root,{withFileTypes:true})){
  const p=join(root,entry.name);
  if(entry.name==='pyodide.mjs')return p;
  if(entry.isDirectory()){const found=find(p);if(found)return found;}
 }
}
const runtime=find(process.argv[2]);
if(!runtime)throw Error('pyodide.mjs not found');
const {loadPyodide}=await import(pathToFileURL(resolve(runtime)).href);
const py=await loadPyodide({indexURL:dirname(resolve(runtime))});
const version=process.argv[3];
if(py.version!==version)throw Error(`runtime version mismatch ${py.version}`);
py.globals.set('source',readFileSync('src/nte_gear_optimizer/rules/opb10.py','utf8'));
py.globals.set('vectors',readFileSync('tests/fixtures/opb10.tsv','utf8'));
const result=py.runPython(`
import types,sys,csv,io,json
module=types.ModuleType('opb10_under_test')
sys.modules[module.__name__]=module
exec(source,module.__dict__)
cases=list(csv.DictReader(io.StringIO(vectors),delimiter='\\t'))
for case in cases:
    result=module.evaluate(case['Input'])
    assert result.rounded==case['ExpectedRounded'],case
    assert result.verdict==case['ExpectedVerdict'],case
assert module.evaluate('1.00500000049999499').verdict=='EQUAL'
json.dumps({'pyodide':${JSON.stringify(version)},'python':sys.version,'vectors_passed':len(cases)})
`);
console.log(result);
