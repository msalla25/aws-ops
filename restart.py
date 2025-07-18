---
- name: Process two files in parallel
  hosts: localhost
  vars:
    file1: "/path/to/file1.json"
    file2: "/path/to/file2.json"

  tasks:
    - name: Get line counts
      ansible.builtin.shell: |
        wc -l < "{{ file1 }}"
        wc -l < "{{ file2 }}"
      register: line_counts
      changed_when: false

    - name: Set maximum lines
      ansible.builtin.set_fact:
        max_lines: "{{ [line_counts.stdout_lines[0]|int, line_counts.stdout_lines[1]|int]|max }}"

    - name: Process records
      include_tasks: process_apis.yaml
      loop: "{{ range(0, max_lines)|list }}"
      loop_control:
        loop_var: line_number


---
- name: Get current lines
  ansible.builtin.set_fact:
    line1: "{{ lookup('file', file1).split('\n')[line_number] | default('') }}"
    line2: "{{ lookup('file', file2).split('\n')[line_number] | default('') }}"

- name: Call first endpoint (if line exists)
  ansible.builtin.uri:
    url: "https://api.example.com/endpoint1"
    method: POST
    body: "{{ line1 }}"
    body_format: json
  when: line1|length > 0

- name: Call second endpoint (if line exists)
  ansible.builtin.uri:
    url: "https://api.example.com/endpoint2"
    method: POST
    body: "{{ line2 }}"
    body_format: json
  when: line2|length > 0