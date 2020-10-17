# Migrating from version 1
Versions 2.0.0 and later are not compatible with previous databases and configuration files!
Chose one of three migration paths:
- [Migrating using the migration script](#migrating-using-the-migration-script-recommended)
    - Recommended
    - Most complete migration
    - Keeps all data from version 1, but does not populate the duration attribute of videos
- [Channel export and import](#channel-export-and-import)
    - Populates the duration attribute of videos, but loses the watched status
- [Start from scratch](#start-from-scratch)
    - Easiest, but you lose all data of version 1

## Migrating using the migration script (Recommended)
You need to follow several steps in order to migrate your subscriptions to 2.0.0 or later.
Unfortunately, videos migrated from version 1 always have the duration attribute set to zero.

*Note: If you adjusted the database location in version 1 you have to adjust the paths used below*

1. Upgrade ytcc to version 2.0.0 or later.
2. Download the migration script from [here](https://github.com/woefe/ytcc/tree/master/scripts/migrate.py).
3. Rename your v1 database.
    ```shell script
    mv ~/.local/share/ytcc/ytcc.db ~/.local/share/ytcc/ytcc.db.v1
    ```
4. Migrate the database.
    ```shell script
    python3 path/to/migrate.py --olddb ~/.local/share/ytcc/ytcc.db.v1 --newdb ~/.local/share/ytcc/ytcc.db
    ```
5. (Optional) Take a look at the [configuration](#configuration) to see what's new and update your config.


## Channel export and import
Warning: with following migration, you will lose the "watched" status of your videos.

1. Export your subscriptions with ytcc 1.8.5 **before** upgrading to 2.0.0 or later
    ```shell script
    ytcc --export-to subscriptions.opml
    ```
2. Upgrade ytcc
3. Rename configuration file and database (e.g. with `mv ~/.config/ytcc ~/.config/ytcc.1`)
4. Import your subscriptions with v2
    ```shell script
    ytcc import subscriptions.opml
    ```
5. (Optional) You might also want to adjust your config to the new format. See [Configuration](#configuration).

## Start from scratch
If you think the procedures described above are not worth the effort, you can start from scratch by removing the `~/.config/ytcc` directory.
