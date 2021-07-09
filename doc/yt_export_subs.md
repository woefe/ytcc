# Exporting your youtube subscriptions to a JSON file

To do export your youtube subscriptions, follow these steps

1. After accessing the website, click on **Create new export and Deselect all.**
2. Scroll down to *Youtube and Youtube Music.*
3. Then click on **All Youtube Data Included** and again,
4. click on 'deselect all' and check only the subscriptions entry.
5. After that, click on **Next**,
6. click on **Create Export**
7. decompress the downloaded .zip file (with a tool such as [7-zip](https://www.7-zip.org/)), you should end up with a json file called `subscriptions.json`.
8. You can now run `ytcc import FILE_PATH` and `ytcc update` (in that order).
