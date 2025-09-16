8import csv
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
        # Read and parse XML 
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

import csv
import xml.etree.ElementTree as ET
from io import StringIO
import copy

def update_nested_xml_attributes(input_csv, template_xml, output_txt):
    """
    Updates nested attributes in XML template from CSV data and writes to text file.
    Each row in CSV creates a separate XML payload.
    """
    try:
        # First, read and parse the template once to get the structure
        template_tree = ET.parse(template_xml)
        template_root = template_tree.getroot()
        
        # Read CSV data
        with open(input_csv, 'r', newline='') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            
            with open(output_txt, 'w') as outfile:
                for row_index, row in enumerate(csv_reader):
                    print(f"Processing row {row_index + 1}: {row}")
                    
                    # Create a DEEP copy of the template for this row
                    current_root = copy.deepcopy(template_root)
                    
                    # Update attributes 'a' and 'b' at any nesting level
                    for elem in current_root.iter():
                        if 'a' in elem.attrib and 'a' in row:
                            elem.attrib['a'] = row['a']
                            print(f"  Updated attribute 'a' to: {row['a']}")
                        if 'b' in elem.attrib and 'b' in row:
                            elem.attrib['b'] = row['b']
                            print(f"  Updated attribute 'b' to: {row['b']}")
                    
                    # Convert to string and minify
                    xml_str = ET.tostring(current_root, encoding='unicode')
                    # Remove extra whitespace and newlines for single-line output
                    xml_str = ' '.join(xml_str.split())
                    
                    outfile.write(xml_str + '\n')
                    print(f"  Written XML payload for row {row_index + 1}")
        
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