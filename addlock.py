import csv
import xml.etree.ElementTree as ET
from io import StringIO

def update_nested_xml_attributes(input_csv, template_xml, output_txt):
    """
    Updates nested attributes in XML template from CSV data and writes to text file.
    
    Args:
        input_csv (str): Path to input CSV file
        template_xml (str): Path to XML template file
        output_txt (str): Path to output text file
    """
    try:
        # Read and parse XML template
        tree = ET.parse(template_xml)
        root = tree.getroot()
        
        # Read CSV data
        with open(input_csv, 'r', newline='') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            
            with open(output_txt, 'w') as outfile:
                for row in csv_reader:
                    # Create a fresh copy of the XML tree for each row
                    current_tree = ET.parse(template_xml)
                    current_root = current_tree.getroot()
                    
                    # Update attributes 'a' and 'b' at any nesting level
                    for elem in current_root.iter():
                        if 'a' in elem.attrib:
                            elem.attrib['a'] = row.get('a', elem.attrib['a'])
                        if 'b' in elem.attrib:
                            elem.attrib['b'] = row.get('b', elem.attrib['b'])
                    
                    # Convert to string and minify
                    xml_str = ET.tostring(current_root, encoding='unicode')
                    # Remove extra whitespace and newlines for single-line output
                    xml_str = ' '.join(xml_str.split())
                    
                    outfile.write(xml_str + '\n')
        
        print(f"Successfully processed {input_csv} to {output_txt}")
        
    except FileNotFoundError as e:
        print(f"File not found: {e}")
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
    except Exception as e:
        print(f"Error occurred: {e}")

def main():
    # Configuration - update these paths as needed
    INPUT_CSV = "input.csv"        # CSV with values for attributes a and b
    TEMPLATE_XML = "template.xml"  # XML template with nested attributes
    OUTPUT_TXT = "output.txt"      # Output file with one XML line per record
    
    update_nested_xml_attributes(INPUT_CSV, TEMPLATE_XML, OUTPUT_TXT)

if __name__ == "__main__":
    main()
stages:
  - generate

generate_xml:
  stage: generate
  image: python:3.9
  script:
    - pip install pandas  # If needed for complex CSV handling
    - python generate_xml.py
  artifacts:
    paths:
      - output.txt
  only:
    changes:
      - input.csv
      - template.xml
      - generate_xml.py