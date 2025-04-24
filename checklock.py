---
- name: Reprocess files by date
  hosts: your_target_server
  vars:
    base_path: "/path/to/your/folders"
    folder_names:
      - folder1
      - folder2
      - folder3
      - folder4
      - folder5
    # This will be populated by the survey input
    target_date: ""

  tasks:
    - name: Find files containing date string in backup folders
      find:
        paths: "{{ base_path }}/{{ item }}_bkp"
        recurse: no
        file_type: file
        patterns: "*{{ target_date }}*"
      register: dated_files
      loop: "{{ folder_names }}"
      loop_control:
        loop_var: current_folder

    - name: Move matching files to processing folders
      command: "mv {{ item.path }} {{ base_path }}/{{ current_folder }}/{{ item.path | basename }}"
      loop: "{{ dated_files.results | selectattr('matched', 'defined') | map(attribute='files') | flatten }}"
      when: item.matched > 0

    - name: Display summary of moved files
      debug:
        msg: |
          Moved {{ item.item }} files:
          {% for file in item.files %}
          - {{ file.path | basename }}
          {% endfor %}
      loop: "{{ dated_files.results | selectattr('matched', 'defined') }}"
      when: item.matched > 0