stages:
  - convert

xml-to-json:
  stage: convert
  image: python:3.9-slim
  before_script:
    - apt-get update && apt-get install -y --no-install-recommends python3-lxml
  script:
    - |
      cat << 'EOF' > convert_xml_to_json.py
      import json
      from lxml import etree
      import sys
      from collections import OrderedDict

      def xml_to_dict(element):
          """Convert XML element to Python dict"""
          result = OrderedDict()
          result['@tag'] = element.tag
          if element.attrib:
              result['@attributes'] = dict(element.attrib)
          if element.text and element.text.strip():
              result['@text'] = element.text.strip()
          
          children = list(element)
          if children:
              for child in children:
                  child_dict = xml_to_dict(child)
                  child_tag = child.tag
                  if child_tag in result:
                      if not isinstance(result[child_tag], list):
                          result[child_tag] = [result[child_tag]]
                      result[child_tag].append(child_dict)
                  else:
                      result[child_tag] = child_dict
          return result

      if __name__ == '__main__':
          if len(sys.argv) != 3:
              print("Usage: python convert_xml_to_json.py <input.xml> <output.json>")
              sys.exit(1)
          
          input_file = sys.argv[1]
          output_file = sys.argv[2]
          
          try:
              tree = etree.parse(input_file)
              root = tree.getroot()
              xml_dict = xml_to_dict(root)
              
              with open(output_file, 'w') as f:
                  json.dump(xml_dict, f, indent=2)
              
              print(f"Successfully converted {input_file} to {output_file}")
          except Exception as e:
              print(f"Error: {str(e)}")
              sys.exit(1)
      EOF
    - python convert_xml_to_json.py standalone.xml config.json
  artifacts:
    paths:
      - config.json
    expire_in: 1 week
deploy:
  stage: deploy
  variables:
    DEPLOY_PATH: "C:\\app"   # change to your app path
  script:
    # Prompt user for credentials (interactive in GitLab UI)
    - echo "Enter AD username:" && read USERNAME
    - echo "Enter password:" && read -s PASSWORD

    # Use SSH with AD credentials (via sshpass for automation)
    - sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$USERNAME@windows-vm.domain.com" "
        cd $DEPLOY_PATH &&
        .venv\\Scripts\\activate &&
        pip install mypkg.whl
      "
script:
  - pwsh -Command "Invoke-Command -ComputerName myvm.domain.com -UseSSL -Port 443 -Credential (Get-Credential) -ScriptBlock { cd C:\app; .venv\Scripts\activate; pip install mypkg.whl }"
deploy:
  stage: deploy
  script:
    - $secpasswd = ConvertTo-SecureString "$env:WIN_PASS" -AsPlainText -Force
    - $creds = New-Object System.Management.Automation.PSCredential ("$env:WIN_USER", $secpasswd)
    - Invoke-Command -ComputerName myvm.domain.com -UseSSL -Port 443 -Credential $creds -ScriptBlock {
        cd C:\app
        .venv\Scripts\activate
        pip install mypkg.whl
      }

network:
  version: 2
  renderer: NetworkManager
  ethernets:
    enp0s3:
      dhcp4: no
      addresses:
        - 192.168.1.100/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 1.1.1.1
