import {useEffect, useState, useRef, useCallback} from 'react';
import {Check, CheckCircle2, ChevronDown, Download, FileSpreadsheet, Loader2, Save, Search, Upload, X} from 'lucide-react';
import {BACKEND_URL, request} from './api';

const normalize = value => value.toLowerCase().replace(/[^a-z0-9]/g, '');
const templateUrl = (table, format) => `${BACKEND_URL.replace(/\/$/, '')}/upload/template/${table}?format=${format}`;

export function ErrorNotice({error, title = 'Unable to complete request'}) {
    if (!error) return null;
    return <div className="entry-error" role="alert"><h4>{title}</h4><p>{error.message}</p>{error.errors?.length > 0 &&
        <ul>{error.errors.map((message, index) => <li key={index}>{message}</li>)}</ul>}</div>;
}

function formatRecordLabel(row) {
    if (!row) return '';
    const id = row.id ?? '';
    if (row.project_code || row.project_name) {
        const parts = [row.project_code, row.project_name].filter(Boolean);
        return `#${id} · ${parts.join(' - ')}`;
    }
    if (row.trip_code || row.trip_name) {
        const parts = [row.trip_code, row.trip_name].filter(Boolean);
        return `#${id} · ${parts.join(' - ')}`;
    }
    if (row.opcode || row.site_name) {
        const parts = [row.opcode, row.site_name].filter(Boolean);
        return `#${id} · ${parts.join(' · ')}`;
    }
    if (row.full_name || row.email) {
        return row.full_name ? `#${id} · ${row.full_name} (${row.email})` : `#${id} · ${row.email}`;
    }
    if (row.firstname || row.lastname) {
        const name = [row.firstname, row.lastname].filter(Boolean).join(' ');
        return row.jobtitle ? `#${id} · ${name} (${row.jobtitle})` : `#${id} · ${name}`;
    }
    if (row.name) {
        return `#${id} · ${row.name}`;
    }
    if (row.species_name || row.common_name) {
        return `#${id} · ${row.species_name || ''}${row.common_name ? ` (${row.common_name})` : ''}`;
    }
    for (const [key, val] of Object.entries(row)) {
        if (key !== 'id' && typeof val === 'string' && val.trim() && !key.toLowerCase().includes('password')) {
            return `#${id} · ${val.trim()}`;
        }
    }
    return `Record #${id}`;
}

function ForeignKeySelect({name, spec, value, onChange, targetTable}) {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState('');
    const [options, setOptions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedRecord, setSelectedRecord] = useState(null);
    const [error, setError] = useState(null);
    const containerRef = useRef(null);
    const searchInputRef = useRef(null);

    // Close dropdown on click outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setOpen(false);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Focus search input when dropdown opens
    useEffect(() => {
        if (open && searchInputRef.current) {
            searchInputRef.current.focus();
        }
    }, [open]);

    // Fetch matching options when dropdown is open or search query changes
    useEffect(() => {
        if (!open) return;
        const controller = new AbortController();
        setLoading(true);
        const timer = setTimeout(() => {
            request(`/tables/${targetTable}?skip=0&limit=50&search=${encodeURIComponent(search)}`, controller.signal)
                .then(res => {
                    setOptions(res.items || []);
                    setLoading(false);
                    setError(null);
                })
                .catch(err => {
                    if (err.name !== 'AbortError') {
                        setError(err.message);
                        setLoading(false);
                    }
                });
        }, 200);
        return () => {
            clearTimeout(timer);
            controller.abort();
        };
    }, [open, search, targetTable]);

    // Resolve record details for currently selected value
    useEffect(() => {
        if (!value) {
            setSelectedRecord(null);
            return;
        }
        const existing = options.find(item => String(item.id) === String(value));
        if (existing) {
            setSelectedRecord(existing);
            return;
        }
        const controller = new AbortController();
        request(`/tables/${targetTable}?skip=0&limit=10&search=${encodeURIComponent(value)}`, controller.signal)
            .then(res => {
                const found = (res.items || []).find(item => String(item.id) === String(value));
                if (found) setSelectedRecord(found);
            })
            .catch(() => {});
        return () => controller.abort();
    }, [value, targetTable, options]);

    const formattedTable = targetTable ? targetTable.replaceAll('_', ' ') : 'record';

    return (
        <div className={`fk-select-container ${open ? 'is-open' : ''}`} ref={containerRef}>
            <input
                id={`capture-${name}`}
                name={name}
                type="text"
                className="fk-hidden-input"
                value={value ?? ''}
                required={spec.required}
                readOnly
                tabIndex={-1}
            />
            <div
                className={`fk-trigger ${value ? 'has-value' : ''}`}
                tabIndex={0}
                role="combobox"
                aria-expanded={open}
                aria-haspopup="listbox"
                onClick={() => setOpen(prev => !prev)}
                onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                        e.preventDefault();
                        setOpen(true);
                    }
                }}
            >
                <div className="fk-trigger-content">
                    {value ? (
                        <span className="fk-selected-label">
                            {selectedRecord ? formatRecordLabel(selectedRecord) : `Selected ID #${value}`}
                        </span>
                    ) : (
                        <span className="fk-placeholder">
                            Select existing {formattedTable}…
                        </span>
                    )}
                </div>
                <div className="fk-trigger-actions">
                    {value && (
                        <button
                            type="button"
                            className="fk-clear-btn"
                            aria-label="Clear selection"
                            title="Clear selection"
                            onClick={e => {
                                e.stopPropagation();
                                onChange('');
                                setSelectedRecord(null);
                                setSearch('');
                            }}
                        >
                            <X size={14} />
                        </button>
                    )}
                    <span className="fk-chevron">
                        <ChevronDown size={15} />
                    </span>
                </div>
            </div>

            {open && (
                <div className="fk-dropdown" role="listbox">
                    <div className="fk-search-bar">
                        <Search size={14} className="fk-search-icon" />
                        <input
                            ref={searchInputRef}
                            type="text"
                            className="fk-search-input"
                            placeholder={`Search ${formattedTable} by name, code, ID…`}
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            onClick={e => e.stopPropagation()}
                            onKeyDown={e => {
                                if (e.key === 'Escape') {
                                    setOpen(false);
                                }
                            }}
                        />
                        {search && (
                            <button
                                type="button"
                                className="fk-search-clear"
                                aria-label="Clear search"
                                onClick={() => setSearch('')}
                            >
                                <X size={13} />
                            </button>
                        )}
                    </div>
                    <div className="fk-options-list">
                        {loading && (
                            <div className="fk-status-item">
                                <Loader2 size={15} className="fk-spinner" />
                                <span>Loading existing {formattedTable}…</span>
                            </div>
                        )}
                        {error && (
                            <div className="fk-status-item error">
                                <span>{error}</span>
                            </div>
                        )}
                        {!loading && !error && options.length === 0 && (
                            <div className="fk-status-item empty">
                                <span>{search ? 'No matching records found.' : `No ${formattedTable} records exist yet.`}</span>
                            </div>
                        )}
                        {!loading && options.map(item => {
                            const isSelected = String(item.id) === String(value);
                            return (
                                <button
                                    key={item.id}
                                    type="button"
                                    role="option"
                                    aria-selected={isSelected}
                                    className={`fk-option-item ${isSelected ? 'selected' : ''}`}
                                    onClick={() => {
                                        onChange(item.id);
                                        setSelectedRecord(item);
                                        setOpen(false);
                                        setSearch('');
                                    }}
                                >
                                    <span className="fk-option-text">
                                        {formatRecordLabel(item)}
                                    </span>
                                    {isSelected && <Check size={15} className="fk-option-check" />}
                                </button>
                            );
                        })}
                    </div>
                    <div className="fk-dropdown-footer">
                        <span>{formattedTable}</span>
                        {options.length > 0 && <small>{options.length} records shown</small>}
                    </div>
                </div>
            )}
        </div>
    );
}

export function FieldControl({name, spec, value, onChange, id, compact = false, className = ''}) {
    if (spec.references) {
        const targetTable = spec.references.split('.').slice(-2, -1)[0] || spec.references.split('.')[0];
        return <ForeignKeySelect
            name={name}
            spec={spec}
            value={value}
            onChange={onChange}
            targetTable={targetTable}
        />;
    }
    const props = {
        id: id || `capture-${name}`,
        name,
        value: value ?? '',
        className: `${className} ${compact ? 'compact-control' : ''}`.trim() || undefined,
        onChange: event => onChange(event.target.value),
        required: spec.required
    };
    if (spec.type === 'bool') {
        const isTrue = (value === true || value === 'true' || value === 1 || value === '1' || String(value).toLowerCase() === 'yes' || String(value).toLowerCase() === 'y' || String(value).toLowerCase() === 't');
        const boolStr = isTrue ? 'true' : 'false';
        return <select {...props} value={boolStr}>
            <option value="false">No</option>
            <option value="true">Yes</option>
        </select>;
    }
    if (spec.multiline && !compact) return <textarea {...props} rows={3} maxLength={spec.max_length}/>;
    const type = name === 'password' ? 'password' : ({
        int: 'number',
        float: 'number',
        date: 'date',
        datetime: 'datetime-local',
        time: 'time'
    }[spec.type] || 'text');
    return <input {...props} type={type}
                  step={spec.type === 'float' ? 'any' : spec.type === 'time' ? '1' : spec.type === 'int' ? '1' : undefined}
                  maxLength={spec.max_length} autoComplete={name === 'password' ? 'new-password' : 'off'}/>;
}

function SingleRecord({table, schema, onSaved}) {
    const getInitialValues = useCallback(() => {
        const init = {};
        if (schema?.fields) {
            for (const [name, spec] of Object.entries(schema.fields)) {
                if (spec.type === 'bool') {
                    init[name] = 'false';
                }
            }
        }
        return init;
    }, [schema]);

    const [values, setValues] = useState(getInitialValues);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const [saved, setSaved] = useState(null);

    useEffect(() => {
        setValues(getInitialValues());
    }, [getInitialValues]);

    async function submit(event) {
        event.preventDefault();
        setBusy(true);
        setError(null);
        setSaved(null);
        try {
            const payload = { ...values };
            if (schema?.fields) {
                for (const [name, spec] of Object.entries(schema.fields)) {
                    if (spec.type === 'bool' && (payload[name] === undefined || payload[name] === null || payload[name] === '')) {
                        payload[name] = 'false';
                    }
                }
            }
            const data = await request(`/upload/record/${table.name}`, undefined, {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
            });
            setSaved(data);
            setValues(getInitialValues());
            onSaved();
        } catch (failure) {
            setError(failure);
        } finally {
            setBusy(false);
        }
    }

    return <div className="entry-content">
        <div className="entry-intro"><h3>Capture a single record</h3><p>Enter the details below. Fields marked * are
            required. Related IDs must refer to existing records.</p></div>
        {saved &&
            <div className="entry-success" role="status"><CheckCircle2 size={18}/>Record #{saved.id} saved successfully.
                You can
                capture another record or view it in Records.</div>}
        <ErrorNotice title="Record capture failed" error={error}/>
        <form onSubmit={submit}>
            <fieldset disabled={busy} className="capture-fields">
                <legend className="sr-only">{table.label} fields</legend>
                {Object.entries(schema.fields).map(([name, spec]) => <div
                    className={spec.multiline ? 'capture-field wide' : 'capture-field'} key={name}>
                    <label htmlFor={`capture-${name}`}>{spec.label}{spec.required &&
                        <span className="required-mark"> *</span>}</label>
                    <FieldControl name={name} spec={spec} value={values[name] ?? ''} onChange={value => {
                        setValues(previous => ({...previous, [name]: value}));
                        setSaved(null);
                    }}/>
                    {spec.references &&
                        <small>Search and select an existing {spec.references.replace('.id', '').replaceAll('_', ' ')} record</small>}
                    {spec.type === 'bool' &&
                        <small>Defaults to No</small>}
                </div>)}
            </fieldset>
            <div className="entry-actions">
                <button className="primary-button" type="submit" disabled={busy}><Save
                    size={16}/>{busy ? 'Saving…' : 'Save record'}</button>
                <button type="button" disabled={busy} onClick={() => {
                    setValues(getInitialValues());
                    setSaved(null);
                    setError(null);
                }}>Clear form
                </button>
            </div>
        </form>
    </div>;
}

function BulkUpload({table, schema, onSaved}) {
    const [file, setFile] = useState(null);
    const [inspection, setInspection] = useState(null);
    const [sheetName, setSheetName] = useState('');
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState('');
    const [fileRevision, setFileRevision] = useState(0);
    const sheet = inspection?.sheets.find(item => item.sheet_name === sheetName);
    const usedColumns = new Set();
    const columnMapping = {};
    for (const [name, spec] of Object.entries(schema.fields)) {
        const isDeploymentFk = name === 'deployment_id' || spec.references === 'deployments.id';
        const source = sheet?.columns.find(column => {
            if (usedColumns.has(column)) return false;
            const normCol = normalize(column);
            if (normCol === normalize(name) || normCol === normalize(spec.label)) return true;
            if (isDeploymentFk && ['opcode', 'deploymentopcode', 'deployment'].includes(normCol)) return true;
            if (name === 'cal_success' && ['success', 'calibrationsuccess', 'calsuccessful', 'calstatus'].includes(normCol)) return true;
            if (spec.lookup_field && normCol === normalize(spec.lookup_field)) return true;
            return false;
        });
        if (source) {
            usedColumns.add(source);
            columnMapping[source] = name;
        }
    }
    const matchedFields = new Set(Object.values(columnMapping));
    const missingRequired = schema.required_fields.filter(name => !matchedFields.has(name));
    const imported = result?.success && result.inserted_rows > 0;

    function chooseSheet(nextSheet) {
        setSheetName(nextSheet.sheet_name);
        setResult(null);
        setError(null);
    }

    async function inspect(event) {
        const selected = event.target.files[0];
        setFile(selected || null);
        setInspection(null);
        setSheetName('');
        setResult(null);
        setError(null);
        if (!selected) return;
        if (!/\.(csv|xlsx|xls)$/i.test(selected.name)) {
            setError(new Error('Choose a CSV or Excel file (.csv, .xlsx, .xls).'));
            return;
        }
        if (selected.size > 10 * 1024 * 1024) {
            setError(new Error('Files must be 10 MB or smaller.'));
            return;
        }
        setBusy('inspect');
        try {
            const form = new FormData();
            form.append('file', selected);
            const data = await request('/upload/inspect', undefined, {method: 'POST', body: form});
            setInspection(data);
            const first = data.sheets.find(item => item.row_count > 0) || data.sheets[0];
            if (first) chooseSheet(first);
            else throw new Error('The file has no worksheets to preview.');
        } catch (failure) {
            setError(failure);
        } finally {
            setBusy('');
        }
    }

    function payload() {
        const form = new FormData();
        form.append('file', file);
        form.append('sheet_name', sheetName);
        form.append('entity_type', table.name);
        form.append('mapping_json', JSON.stringify(columnMapping));
        form.append('import_mode', 'strict');
        return form;
    }

    async function commit() {
        setBusy('validate');
        setError(null);
        setResult(null);
        try {
            if (missingRequired.length > 0) {
                throw new Error(`Missing required columns: ${missingRequired.map(name => schema.fields[name].label).join(', ')}. Use the template column headers and upload the corrected file.`);
            }
            if (!matchedFields.size) {
                throw new Error('No spreadsheet columns match this table. Use the CSV or Excel template and upload the corrected file.');
            }
            const validation = await request('/upload/validate', undefined, {method: 'POST', body: payload()});
            if (validation.error_count > 0 || validation.valid_count === 0) {
                const failure = new Error('No records imported. Correct the spreadsheet errors and upload the file again.');
                const invalidRows = validation.rows.filter(row => row.errors.length > 0);
                failure.errors = invalidRows.slice(0, 100).map(row => `Row ${row.row_number}: ${row.errors.join(' ')}`);
                if (invalidRows.length > 100) failure.errors.push('Showing the first 100 rows with errors.');
                throw failure;
            }
            setBusy('commit');
            const data = await request('/upload/commit', undefined, {method: 'POST', body: payload()});
            setResult(data);
            if (data.success && data.inserted_rows > 0) onSaved();
        } catch (failure) {
            setError(failure);
        } finally {
            setBusy('');
        }
    }

    function reset() {
        setFile(null);
        setInspection(null);
        setSheetName('');
        setResult(null);
        setError(null);
        setFileRevision(value => value + 1);
    }

    return <div className="entry-content">
        <div className="entry-intro"><h3>Upload records from a spreadsheet</h3><p>Choose a CSV or Excel file, review the
            preview, then import into {table.label.toLowerCase()}. Use the template column headers. For deployment fields, you can use the opcode (e.g. BRUV_001) or ID. Extra columns are
            ignored.</p></div>
        <div className="template-links"><span>Start with a template:</span><a
            href={templateUrl(table.name, 'csv')}><Download size={15}/>CSV template</a><a
            href={templateUrl(table.name, 'xlsx')}><Download size={15}/>Excel template</a></div>
        <fieldset disabled={Boolean(busy) || Boolean(result)} className="upload-controls">
            <legend className="sr-only">Upload file and preview</legend>
            <label className="upload-file"><FileSpreadsheet size={25}/><span><strong>Choose a file</strong><small>CSV, XLSX or XLS · Up to 10 MB and 10,000 rows</small></span><input
                key={fileRevision} aria-label="CSV or Excel file" type="file" accept=".csv,.xlsx,.xls"
                onChange={inspect} onClick={event => {
                event.currentTarget.value = '';
            }}/></label>
            {busy === 'inspect' && <p role="status" className="muted">Reading spreadsheet…</p>}
            {inspection && <>
                <div className="sheet-picker"><label htmlFor="upload-sheet">Worksheet</label><select id="upload-sheet"
                                                                                                     value={sheetName}
                                                                                                     onChange={event => chooseSheet(inspection.sheets.find(item => item.sheet_name === event.target.value))}>{inspection.sheets.map(item =>
                    <option key={item.sheet_name}
                            value={item.sheet_name}>{item.sheet_name} ({item.row_count.toLocaleString()} rows)</option>)}</select><span
                    className="muted">{file.name}</span></div>
                {sheet?.error && <ErrorNotice title="Upload failed" error={{message: sheet.error}}/>}
                {sheet?.preview.length > 0 && <div className="upload-preview table-scroll">
                    <table>
                        <caption>Preview — first {sheet.preview.length} of {sheet.row_count.toLocaleString()} rows
                        </caption>
                        <thead>
                        <tr>{sheet.columns.map(column => <th key={column} scope="col">{column}</th>)}</tr>
                        </thead>
                        <tbody>{sheet.preview.map((row, index) => <tr key={index}>{sheet.columns.map(column => <td
                            key={column}>{row[column] || '—'}</td>)}</tr>)}</tbody>
                    </table>
                </div>}
            </>}
        </fieldset>
        <ErrorNotice title="Upload failed" error={error}/>
        {inspection && !result && sheet?.row_count > 0 && <div className="entry-actions">
            <button className="primary-button" disabled={Boolean(busy)} onClick={commit}><Upload
                size={16}/>{busy === 'validate' ? 'Checking records…' : busy === 'commit' ? 'Importing…' : `Import ${sheet.row_count.toLocaleString()} records`}
            </button>
        </div>}
        {result && <section className={imported ? 'import-result entry-success' : 'import-result entry-error'}
                            role={imported ? 'status' : 'alert'}>
            <h4>{imported ? 'Upload successful' : 'Upload failed'}</h4>
            <p>{imported ? `Successfully imported ${result.inserted_rows.toLocaleString()} records into ${table.label.toLowerCase()}.` : 'No records imported. Correct the spreadsheet and try again.'}</p>{result.error_details?.length > 0 &&
            <ul>{result.error_details.slice(0, 100).map(item => <li key={item.row}>
                <strong>Row {item.row}:</strong> {item.errors.join(' ')}</li>)}</ul>}
            <button onClick={reset}>Upload another file</button>
        </section>}
    </div>;
}

export default function DataEntry({table, mode, onSaved}) {
    const [state, setState] = useState({loading: true, schemas: null, error: null});
    const [attempt, setAttempt] = useState(0);
    useEffect(() => {
        const controller = new AbortController();
        request('/upload/schemas', controller.signal)
            .then(schemas => setState({loading: false, schemas, error: null}))
            .catch(error => {
                if (error.name !== 'AbortError') setState({loading: false, schemas: null, error});
            });
        return () => controller.abort();
    }, [attempt]);
    if (state.loading) return <div className="empty-state" role="status">Loading entry fields…</div>;
    if (state.error) return <div className="entry-content"><ErrorNotice error={state.error}/>
        <button onClick={() => {
            setState({loading: true, schemas: null, error: null});
            setAttempt(value => value + 1);
        }}>Try again
        </button>
    </div>;
    const sourceSchema = state.schemas[table.name];
    if (!sourceSchema) return <div className="empty-state">Data entry is unavailable for this table.</div>;
    const schema = table.name === 'projects' ? {
        ...sourceSchema,
        fields: Object.fromEntries(Object.entries(sourceSchema.fields).filter(([name]) => name !== 'name')),
        required_fields: sourceSchema.required_fields.filter(name => name !== 'name'),
    } : sourceSchema;
    return mode === 'capture' ? <SingleRecord key={table.name} table={table} schema={schema} onSaved={onSaved}/> :
        <BulkUpload key={table.name} table={table} schema={schema} onSaved={onSaved}/>;
}
