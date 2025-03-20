import pandas as pd
import json

def load_json(file_path):
    """Load JSON data from a file."""
    with open(file_path, 'r') as file:
        return json.load(file)

def update_json_payload(json_payload, csv_row):
    """Update JSON payload with data from a CSV row."""
    # Update top-level fields
    if 'field1' in json_payload:
        json_payload['field1'] = csv_row['Column1']
    if 'field2' in json_payload:
        json_payload['field2'] = csv_row['Column2']
    
    # Update nested fields under 'nested_field'
    if 'nested_field' in json_payload and isinstance(json_payload['nested_field'], dict):
        json_payload['nested_field']['nested_field1'] = csv_row['Column3']
        json_payload['nested_field']['nested_field2'] = csv_row['Column4']
        json_payload['nested_field']['nested_field3'] = csv_row['Column5']
        
        # Update deeply nested fields under 'nested_field.deeply_nested_field'
        if 'deeply_nested_field' in json_payload['nested_field'] and isinstance(json_payload['nested_field']['deeply_nested_field'], dict):
            json_payload['nested_field']['deeply_nested_field']['deeply_nested_field1'] = csv_row['Column6']
            json_payload['nested_field']['deeply_nested_field']['deeply_nested_field2'] = csv_row['Column7']
    
    # Update nested fields under 'another_nested_field'
    if 'another_nested_field' in json_payload and isinstance(json_payload['another_nested_field'], dict):
        json_payload['another_nested_field']['nested_field4'] = csv_row['Column8']
        json_payload['another_nested_field']['nested_field5'] = csv_row['Column9']
    
    return json_payload

def main(json_file, csv_file, output_file):
    """Main function to process JSON and CSV files."""
    # Load JSON template
    json_payload_template = load_json(json_file)

    # Load CSV data
    csv_data = pd.read_csv(csv_file)

    # Process each row in CSV and update JSON payload
    updated_payloads = []
    for _, row in csv_data.iterrows():
        updated_payload = update_json_payload(json_payload_template.copy(), row)
        updated_payloads.append(updated_payload)

    # Save updated payloads to a text file
    with open(output_file, 'w') as file:
        for payload in updated_payloads:
            file.write(json.dumps(payload) + '\n')

    print(f"Updated JSON payloads saved to {output_file}")

# File paths
json_file = 'sample_payload.json'  # Path to your JSON file
csv_file = 'data_fields.csv'       # Path to your CSV file
output_file = 'output_payloads.txt'  # Path to the output text file

# Run the script
if __name__ == "__main__":
    main(json_file, csv_file, output_file)