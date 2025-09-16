import csv
import re

def update_nested_xml_attributes(input_csv, template_xml, output_txt):
    """
    Updates nested attributes in XML template from CSV data using string replacement.
    This approach ensures values are actually updated.
    """
    try:
        # Read the template XML as text
        with open(template_xml, 'r') as f:
            template_content = f.read()
        
        # Read CSV data
        with open(input_csv, 'r', newline='') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            
            with open(output_txt, 'w') as outfile:
                for row_index, row in enumerate(csv_reader):
                    print(f"Processing row {row_index + 1}: {row}")
                    
                    # Start with fresh template for each row
                    xml_content = template_content
                    
                    # Replace ALL occurrences of attributes a and b using regex
                    # This handles both: a="value" and a='value'
                    if 'a' in row:
                        xml_content = re.sub(
                            r'a=([\'"])(.*?)\1', 
                            f'a=\\1{row["a"]}\\1', 
                            xml_content
                        )
                        print(f"  Replaced attribute 'a' with: {row['a']}")
                    
                    if 'b' in row:
                        xml_content = re.sub(
                            r'b=([\'"])(.*?)\1', 
                            f'b=\\1{row["b"]}\\1', 
                            xml_content
                        )
                        print(f"  Replaced attribute 'b' with: {row['b']}")
                    
                    # Minify the XML (remove extra whitespace and newlines)
                    xml_content = re.sub(r'>\s+<', '><', xml_content)
                    xml_content = re.sub(r'\s+', ' ', xml_content).strip()
                    
                    outfile.write(xml_content + '\n')
                    print(f"  Written XML payload for row {row_index + 1}")
                    print(f"  Sample output: {xml_content[:100]}...")
        
        print(f"Successfully processed {input_csv} to {output_txt}")
        
    except FileNotFoundError as e:
        print(f"File not found: {e}")
    except Exception as e:
        print(f"Error occurred: {e}")

def main():
    INPUT_CSV = "input.csv"
    TEMPLATE_XML = "template.xml"
    OUTPUT_TXT = "output.txt"
    
    update_nested_xml_attributes(INPUT_CSV, TEMPLATE_XML, OUTPUT_TXT)

if __name__ == "__main__":
    main()