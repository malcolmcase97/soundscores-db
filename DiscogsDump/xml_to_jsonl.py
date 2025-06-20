import json
import os
import xml.etree.ElementTree as ET

def convert_xml_to_jsonl(xml_file_path, output_dir, entry_tag):
    output_file_path = os.path.join(output_dir, f"{entry_tag}s.jsonl")

    context = ET.iterparse(xml_file_path, events=('end',))
    with open(output_file_path, 'w', encoding='utf-8') as out_file:
        count = 0
        for event, elem in context:
            if elem.tag == entry_tag:
                entry = xml_element_to_dict(elem)
                json.dump(entry, out_file, ensure_ascii=False)
                out_file.write('\n')
                elem.clear()
                count += 1
                if count % 10000 == 0:
                    print(f"\rWrote {count} entries...", end="", flush=True)

    print(f"\n✅ Converted {xml_file_path} to {output_file_path}")

def xml_element_to_dict(elem):
    def inner(e):
        result = {}

        # Include attributes (like id="...")
        result.update(e.attrib)

        # If the element has no children, return text (or text + attributes)
        if len(e) == 0:
            text = e.text.strip() if e.text else None
            return text if not result else {**result, "value": text}

        for child in e:
            tag = child.tag
            value = inner(child)
            if tag in result:
                if isinstance(result[tag], list):
                    result[tag].append(value)
                else:
                    result[tag] = [result[tag], value]
            else:
                result[tag] = value
        return result

    return {elem.tag: inner(elem)}

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert Discogs XML to JSONL")
    parser.add_argument("xml", help="Path to XML file (e.g., artists.xml)")
    parser.add_argument("-o", "--output", default=".", help="Output directory")
    parser.add_argument("-t", "--tag", required=True, help="Entry tag (e.g., artist, label, release, master)")

    args = parser.parse_args()
    convert_xml_to_jsonl(args.xml, args.output, args.tag)
