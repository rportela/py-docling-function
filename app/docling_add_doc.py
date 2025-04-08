import copy
from docling_core.types.doc.document import (
    DoclingDocument,
    TitleItem,
    SectionHeaderItem,
    ListItem,
    CodeItem,
    FormulaItem,
    TableItem,
    PictureItem,
    KeyValueItem,
    FormItem,
    GroupItem,
)
from docling_core.types.doc.labels import GroupLabel


def _merge_node(
    target_doc: DoclingDocument, target_parent, source_node, source_doc: DoclingDocument
):
    """
    Recursively merge one node (and its subtree) from the source document into the target document.

    Parameters:
      target_doc (DoclingDocument): The document which is being added to.
      target_parent: The parent node in the target document.
      source_node: The node from the source document to merge.
      source_doc (DoclingDocument): The full source document (used for resolving references).

    Returns:
      The new node created in the target document.
    """

    # Helper to extract a single provenance item (if available)
    def get_prov(node):
        return (
            node.prov[0] if getattr(node, "prov", None) and len(node.prov) > 0 else None
        )

    new_item = None

    # Use type checking to decide which add_* method to invoke.
    if isinstance(source_node, TitleItem):
        new_item = target_doc.add_title(
            text=source_node.text,
            orig=source_node.orig,
            prov=get_prov(source_node),
            parent=target_parent,
            formatting=source_node.formatting,
            hyperlink=source_node.hyperlink,
        )
    elif isinstance(source_node, SectionHeaderItem):
        new_item = target_doc.add_heading(
            text=source_node.text,
            orig=source_node.orig,
            level=source_node.level,
            prov=get_prov(source_node),
            parent=target_parent,
            formatting=source_node.formatting,
            hyperlink=source_node.hyperlink,
        )
    elif isinstance(source_node, ListItem):
        new_item = target_doc.add_list_item(
            text=source_node.text,
            enumerated=source_node.enumerated,
            marker=source_node.marker,
            orig=source_node.orig,
            prov=get_prov(source_node),
            parent=target_parent,
            formatting=source_node.formatting,
            hyperlink=source_node.hyperlink,
        )
    elif isinstance(source_node, CodeItem):
        new_item = target_doc.add_code(
            text=source_node.text,
            code_language=source_node.code_language,
            orig=source_node.orig,
            prov=get_prov(source_node),
            parent=target_parent,
            formatting=source_node.formatting,
            hyperlink=source_node.hyperlink,
        )
    elif isinstance(source_node, FormulaItem):
        new_item = target_doc.add_formula(
            text=source_node.text,
            orig=source_node.orig,
            prov=get_prov(source_node),
            parent=target_parent,
            formatting=source_node.formatting,
            hyperlink=source_node.hyperlink,
        )
    elif isinstance(source_node, TableItem):
        # If at least one caption exists, choose the first one.
        caption = (
            source_node.captions[0].resolve(source_doc)
            if source_node.captions
            else None
        )
        new_item = target_doc.add_table(
            data=copy.deepcopy(source_node.data),
            caption=caption,
            prov=get_prov(source_node),
            parent=target_parent,
            label=source_node.label,
        )
    elif isinstance(source_node, PictureItem):
        caption = (
            source_node.captions[0].resolve(source_doc)
            if source_node.captions
            else None
        )
        new_item = target_doc.add_picture(
            annotations=copy.deepcopy(source_node.annotations),
            image=copy.deepcopy(source_node.image),
            caption=caption,
            prov=get_prov(source_node),
            parent=target_parent,
        )
    elif isinstance(source_node, KeyValueItem):
        new_item = target_doc.add_key_values(
            graph=copy.deepcopy(source_node.graph),
            prov=get_prov(source_node),
            parent=target_parent,
        )
    elif isinstance(source_node, FormItem):
        new_item = target_doc.add_form(
            graph=copy.deepcopy(source_node.graph),
            prov=get_prov(source_node),
            parent=target_parent,
        )
    elif isinstance(source_node, GroupItem):
        # For groups we use the add_group method.
        # Pass group label only if it is an instance of GroupLabel.
        group_label = (
            source_node.label if isinstance(source_node.label, GroupLabel) else None
        )
        new_item = target_doc.add_group(
            label=group_label,
            name=getattr(source_node, "name", None),
            parent=target_parent,
        )
    else:
        # Fallback: if the node has a text attribute we add it as a generic text item.
        if hasattr(source_node, "text"):
            new_item = target_doc.add_text(
                label=source_node.label,
                text=source_node.text,
                orig=source_node.orig,
                prov=get_prov(source_node),
                parent=target_parent,
                formatting=source_node.formatting,
                hyperlink=source_node.hyperlink,
            )

    # Now, if we created a new item, merge all its children recursively.
    if new_item is not None:
        for child_ref in source_node.children:
            source_child = child_ref.resolve(source_doc)
            _merge_node(target_doc, new_item, source_child, source_doc)

    return new_item


def docling_add_doc(target: DoclingDocument, source: DoclingDocument) -> None:
    """
    Merge all elements from the source DoclingDocument into the target DoclingDocument.

    This function iterates over the top-level items in the source document's body and
    copies their entire subtree into the target document using the target document's
    add_* methods. (Note that merging of pages or the furniture section is not handled here.)

    Parameters:
      target (DoclingDocument): The document that will receive the new elements.
      source (DoclingDocument): The document whose elements will be added into target.

    Returns:
      None
    """
    # Iterate over each top-level item in the source document's body.
    for ref in source.body.children:
        source_node = ref.resolve(source)
        _merge_node(target, target.body, source_node, source)
