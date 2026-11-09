# Data management

The left sidebar lists all 14 application tables with live record counts. Select a table to browse its columns and records, search text fields, and paginate through results. Use **Refresh counts** to reload the catalog and selected table. The sidebar supports filtering table names.

Unavailable counts display `—`; empty tables display `0`. Password columns are excluded from the records API. On small screens, use the menu button to open the sidebar.

Select a table, then use **Single record** to capture one record or **Bulk upload** to import CSV, XLSX or XLS files. Upload logs are generated automatically and can only be browsed.

Single-record forms use the current database model fields and show required fields with an asterisk. Related IDs must refer to existing records. Successful saves refresh the table counts.

For bulk uploads, download a CSV or Excel template, fill it in, then choose the file. Select an Excel worksheet, review the preview and click **Import records**. Columns are matched automatically using field names or labels; capitalization, spaces and underscores are ignored. Extra columns are ignored. Validation runs automatically before saving. Any validation or database error cancels the entire import and displays an **Upload failed** message with the available row errors. Successful imports display **Upload successful** and refresh the record counts. Imports and their upload logs are saved in one transaction.

Files are limited to 10 MB and 10,000 rows per worksheet. Use unique column headers. Dates use `YYYY-MM-DD`, times use `HH:MM:SS`, and booleans accept Yes/No or True/False. Blank optional values use defaults or remain empty; blank rows are skipped. CSV text identifiers preserve leading zeros; in Excel, store such identifiers as text. User passwords are hashed when saved.

## Run locally

From `app/frontend`, run `npm install` if needed, then `npm run dev`. The FastAPI backend must also be running.

The frontend defaults to `http://127.0.0.1:8001`. To use another backend, set `VITE_BACKEND_URL` in `.env.local`, then restart Vite.

## Checks

- Frontend: `npm run build` and `npm run lint`.
- Table-browser and data-entry APIs: from `app/backend`, run `python -m pytest browser_tests -q` with the configured project interpreter. Tests use an isolated SQLite database.

The backend exposes `GET /tables/` for table counts and `GET /tables/{table_name}?skip=0&limit=50&search=` for records. Browsing uses SQLAlchemy Core to avoid unrelated ORM relationship errors and reflects the installed database columns.

Data entry uses `GET /upload/schemas`, `POST /upload/record/{entity_type}`, `POST /upload/inspect`, `POST /upload/validate`, and `POST /upload/commit`. CSV and Excel templates are available at `GET /upload/template/{entity_type}?format=csv|xlsx`. Install the backend requirements to enable spreadsheet parsing, including `xlrd` for legacy XLS files.
