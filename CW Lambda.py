---
- name: Connect to Managed Automation URL using PFX and CA certificates
  hosts: localhost
  gather_facts: no
  vars:
    ma_url: "{{ survey_ma_url }}"  # MA URL from survey
    pfx_password: "{{ survey_pfx_password }}"  # PFX password from survey
    pfx_file_path: "/opt/certs/certificate.pfx"  # Path to the PFX file
    ca_cert_file_path: "/opt/certs/ca_certs.pem"  # Path to the CA certificates file
    certs_dir: "/opt/certs/processed"  # Directory for processed certificates

  tasks:
    - name: Ensure certificates directory exists
      file:
        path: "{{ certs_dir }}"
        state: directory
        mode: '0700'

    - name: Ensure PFX file exists
      stat:
        path: "{{ pfx_file_path }}"
      register: pfx_file

    - name: Fail if PFX file does not exist
      fail:
        msg: "PFX file not found at {{ pfx_file_path }}"
      when: not pfx_file.stat.exists

    - name: Ensure CA certificates file exists
      stat:
        path: "{{ ca_cert_file_path }}"
      register: ca_cert_file

    - name: Fail if CA certificates file does not exist
      fail:
        msg: "CA certificates file not found at {{ ca_cert_file_path }}"
      when: not ca_cert_file.stat.exists

    - name: Extract certificate and key from PFX file using OpenSSL
      shell: |
        openssl pkcs12 -in "{{ pfx_file_path }}" -out "{{ certs_dir }}/ma_cert.pem" -nodes -password pass:"{{ pfx_password }}"
      args:
        executable: /bin/bash
      register: pfx_extract

    - name: Fail if PFX extraction fails
      fail:
        msg: "Failed to extract certificate and key from PFX file"
      when: pfx_extract.rc != 0

    - name: Combine extracted certificate with CA certificates
      shell: |
        cat "{{ certs_dir }}/ma_cert.pem" "{{ ca_cert_file_path }}" > "{{ certs_dir }}/combined_cert.pem"
      args:
        executable: /bin/bash
      register: combine_certs

    - name: Fail if combining certificates fails
      fail:
        msg: "Failed to combine extracted certificate with CA certificates"
      when: combine_certs.rc != 0

    - name: Connect to MA URL using the combined certificate and key
      uri:
        url: "{{ ma_url }}"
        method: GET
        client_cert: "{{ certs_dir }}/combined_cert.pem"
        client_key: "{{ certs_dir }}/ma_cert.pem"
        validate_certs: yes
      register: ma_response

    - name: Display MA URL response
      debug:
        var: ma_response

    - name: Clean up processed certificates
      file:
        path: "{{ certs_dir }}"
        state: absent