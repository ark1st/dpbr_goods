"""Page-level optional content shared by the current A3 generator."""
def mark_pdf_layers(page, layer_streams):
    """Use page-level optional content, which VectorCraft imports as layers."""
    doc = page.parent
    resources = int(doc.xref_get_key(page.xref, 'Resources')[1].split()[0])
    properties = ' '.join(f'/L{layer} {layer} 0 R' for layer in layer_streams)
    doc.xref_set_key(resources, 'Properties', f'<< {properties} >>')
    marked = [
        f'/OC /L{layer} BDC\n'.encode() + b'\n'.join(streams) + b'\nEMC'
        for layer, streams in layer_streams.items()
    ]
    content = page.get_contents()[0]
    page.set_contents(content)
    doc.update_stream(content, b'\n'.join(marked))
