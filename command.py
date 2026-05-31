# Keeps tokens out of shell history
export AAP_SRC_TOKEN='source-pat'
export AAP_DST_TOKEN='dest-pat'

# Dry run
python3 aap_migrate_surveys_schedules.py \
    --src-host https://aap24.yourco.com \
    --dst-host https://aap25.yourco.com \
    --org "My Organization" --insecure

# Apply
python3 aap_migrate_surveys_schedules.py ... --org "My Organization" --commit --insecure
