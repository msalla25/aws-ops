python3 aap_migrate_surveys_schedules.py \
    --src-host https://aap24.yourco.com \
    --dst-host https://aap25.yourco.com \
    --src-org "Old Org Name" --dst-org "New Org Name" \
    --insecure              # dry run

# then add --commit
