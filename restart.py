---
- name: Process two JSON files alternately
  hosts: localhost
  vars:
    file1: "/path/to/file1.txt"
    file2: "/path/to/file2.txt"

  tasks:
    - name: Read both files into variables
      ansible.builtin.set_fact:
        payloads1: "{{ lookup('file', file1).split('\n') | select('match', '.+') | list }}"
        payloads2: "{{ lookup('file', file2).split('\n') | select('match', '.+') | list }}"
        max_lines: "{{ [payloads1|length, payloads2|length]|max }}"

    - name: Process records
      include_tasks: process_apis.yaml
      loop: "{{ range(0, max_lines)|list }}"
      loop_control:
        loop_var: index


---
- name: Call first endpoint
  ansible.builtin.uri:
    url: "https://api.example.com/endpoint1"
    method: POST
    body: "{{ payloads1[index] if index < payloads1|length else '{}' }}"
    body_format: json
    status_code: 200

- name: Call second endpoint
  ansible.builtin.uri:
    url: "https://api.example.com/endpoint2"
    method: POST
    body: "{{ payloads2[index] if index < payloads2|length else '{}' }}"
    body_format: json
    status_code: 200