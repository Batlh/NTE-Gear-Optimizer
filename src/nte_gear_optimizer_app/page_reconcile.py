"""Keep unchanged page children in place; Kivy-independent ordering policy."""


def reconcile_children(container, desired):
    if len({id(w) for w in desired}) != len(desired):
        raise ValueError('A page cannot contain the same widget twice')
    target = list(reversed(desired))
    mutations = 0
    for child in list(container.children):
        if child not in target:
            container.remove_widget(child)
            mutations += 1
    for index, child in enumerate(target):
        if index < len(container.children) and container.children[index] is child:
            continue
        if child.parent is container:
            container.remove_widget(child)
        elif child.parent is not None:
            raise ValueError('Cannot steal a widget from a different page')
        container.add_widget(child, index=index)
        mutations += 1
    return mutations
