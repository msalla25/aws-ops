import csv
import re

# Read the XML template
with open('template.xml', 'r') as file:
    template = file.read()

# Read CSV and generate XML payloads
with open('input.csv', 'r') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    with open('output.txt', 'w') as output_file:
        for row in csv_reader:
            xml_content = template
            for key, value in row.items():
                xml_content = xml_content.replace(f'${{{key}}}', value)
            # Minify XML: remove newlines and extra spaces
            xml_content = re.sub(r'>\s+<', '><', xml_content).strip()
            output_file.write(xml_content + '\n')

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