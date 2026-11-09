import { useEffect, useState, useMemo } from 'react';
import { Pencil, Edit2, Save, X, CheckCircle2, AlertCircle, RotateCcw, Trash2, AlertTriangle } from 'lucide-react';
import { request } from './api';
import { FieldControl, ErrorNotice } from './DataEntry';

export function EditRecordModal({ table, record, onClose, onSaved }) {
  const [schema, setSchema] = useState(null);
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    request('/upload/schemas', controller.signal)
      .then(schemas => {
        const tableSchema = schemas[table.name];
        setSchema(tableSchema || null);
        if (record) {
          // Pre-populate fields from the existing record
          const initial = {};
          if (tableSchema) {
            for (const [fieldName, spec] of Object.entries(tableSchema.fields)) {
              if (record[fieldName] !== undefined && record[fieldName] !== null) {
                initial[fieldName] = record[fieldName];
              } else if (spec.type === 'bool') {
                initial[fieldName] = false;
              }
            }
          }
          setValues(initial);
        }
      })
      .catch(err => {
        if (err.name !== 'AbortError') setError(err);
      });
    return () => controller.abort();
  }, [table.name, record]);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = { ...values };
      if (schema?.fields) {
        for (const [name, spec] of Object.entries(schema.fields)) {
          if (spec.type === 'bool' && (payload[name] === undefined || payload[name] === null || payload[name] === '')) {
            payload[name] = false;
          }
        }
      }
      const data = await request(`/upload/record/${table.name}/${record.id}`, undefined, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setSuccess(data.message || 'Record updated successfully.');
      setTimeout(() => {
        onSaved();
        onClose();
      }, 700);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-window" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <Pencil size={18} className="modal-title-icon" />
            <div>
              <h3>Edit {table.label}: #{record.id}{record._record_label ? ` (${record._record_label})` : ''}</h3>
              <p className="modal-subtitle">Update record attributes and save changes.</p>
            </div>
          </div>
          <button className="modal-close-btn" aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={submit} className="modal-form">
          <div className="modal-body">
            {success && (
              <div className="entry-success" role="status">
                <CheckCircle2 size={18} />
                <span>{success}</span>
              </div>
            )}
            <ErrorNotice title="Failed to update record" error={error} />

            {!schema && !error && (
              <div className="modal-loading">Loading fields…</div>
            )}

            {schema && (
              <fieldset disabled={busy} className="capture-fields">
                <legend className="sr-only">Edit fields for {table.label}</legend>
                {Object.entries(schema.fields).map(([name, spec]) => (
                  <div
                    key={name}
                    className={spec.multiline ? 'capture-field wide' : 'capture-field'}
                  >
                    <label htmlFor={`edit-${name}`}>
                      {spec.label}
                      {spec.required && <span className="required-mark"> *</span>}
                    </label>
                    <FieldControl
                      name={name}
                      spec={spec}
                      value={values[name] ?? ''}
                      onChange={val => {
                        setValues(prev => ({ ...prev, [name]: val }));
                        setError(null);
                      }}
                    />
                    {spec.references && (
                      <small>Select from existing {spec.references.replace('.id', '').replaceAll('_', ' ')} records</small>
                    )}
                    {spec.type === 'bool' && (
                      <small>Defaults to No</small>
                    )}
                  </div>
                ))}
              </fieldset>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="ghost-button" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button type="submit" className="primary-button" disabled={busy || !schema}>
              <Save size={16} />
              {busy ? 'Saving changes…' : 'Save changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function BulkEditModal({ table, records = [], selectedIds = [], onClose, onSaved }) {
  const [schema, setSchema] = useState(null);
  const [rowsData, setRowsData] = useState({});
  const [originalData, setOriginalData] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const targetRecords = useMemo(() => {
    if (records && records.length > 0) return records;
    if (selectedIds && selectedIds.length > 0) {
      return selectedIds.map(id => ({ id }));
    }
    return [];
  }, [records, selectedIds]);

  useEffect(() => {
    const controller = new AbortController();
    request('/upload/schemas', controller.signal)
      .then(schemas => {
        const tableSchema = schemas[table.name];
        setSchema(tableSchema || null);
        if (tableSchema) {
          const fieldKeys = Object.keys(tableSchema.fields);

          const initRows = {};
          const initOriginal = {};
          for (const rec of targetRecords) {
            initRows[rec.id] = {};
            initOriginal[rec.id] = {};
            for (const f of fieldKeys) {
              const val = rec[f] !== undefined && rec[f] !== null ? rec[f] : '';
              initRows[rec.id][f] = val;
              initOriginal[rec.id][f] = val;
            }
          }
          setRowsData(initRows);
          setOriginalData(initOriginal);
        }
      })
      .catch(err => {
        if (err.name !== 'AbortError') setError(err);
      });
    return () => controller.abort();
  }, [table.name, targetRecords]);

  function handleCellChange(recordId, fieldName, value) {
    setRowsData(prev => ({
      ...prev,
      [recordId]: {
        ...(prev[recordId] || {}),
        [fieldName]: value,
      },
    }));
    setError(null);
  }

  function handleResetRow(recordId) {
    if (!originalData[recordId]) return;
    setRowsData(prev => ({
      ...prev,
      [recordId]: { ...originalData[recordId] },
    }));
    setError(null);
  }

  function isCellModified(recordId, fieldName) {
    const current = rowsData[recordId]?.[fieldName];
    const orig = originalData[recordId]?.[fieldName];
    return String(current ?? '') !== String(orig ?? '');
  }

  function isRowModified(recordId) {
    if (!schema?.fields) return false;
    return Object.keys(schema.fields).some(f => isCellModified(recordId, f));
  }

  const modifiedList = useMemo(() => {
    if (!schema?.fields) return [];
    const list = [];
    for (const rec of targetRecords) {
      if (isRowModified(rec.id)) {
        const updates = {};
        for (const f of Object.keys(schema.fields)) {
          if (isCellModified(rec.id, f)) {
            updates[f] = rowsData[rec.id]?.[f];
          }
        }
        list.push({ id: rec.id, ...updates });
      }
    }
    return list;
  }, [rowsData, originalData, schema, targetRecords]);

  const modifiedCount = modifiedList.length;

  async function submit(event) {
    event.preventDefault();
    if (modifiedCount === 0) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = {
        records: modifiedList,
      };
      const data = await request(`/upload/records/${table.name}/bulk`, undefined, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setSuccess(data.message || `Successfully updated ${modifiedCount} records.`);
      setTimeout(() => {
        onSaved();
        onClose();
      }, 700);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-window modal-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <Edit2 size={20} className="modal-title-icon" />
            <div>
              <h3>Bulk Edit {table.label} Records</h3>
              <p className="modal-subtitle">
                Displaying <strong>{targetRecords.length}</strong> records. Manually edit any necessary columns below and save with one button.
              </p>
            </div>
          </div>
          <button className="modal-close-btn" aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={submit} className="modal-form">
          <div className="modal-body bulk-modal-body">
            {success && (
              <div className="entry-success" role="status">
                <CheckCircle2 size={18} />
                <span>{success}</span>
              </div>
            )}
            <ErrorNotice title="Bulk update failed" error={error} />

            {!schema && !error && (
              <div className="modal-loading">Loading records and schema…</div>
            )}

            {schema && (
              <div className="bulk-grid-container">
                <table className="bulk-grid-table">
                  <thead>
                    <tr>
                      <th className="col-sticky-id">ID</th>
                      {Object.entries(schema.fields).map(([name, spec]) => (
                        <th key={name} title={spec.description || spec.label}>
                          <span className="col-header-label">{spec.label}</span>
                          {spec.required && <span className="required-mark"> *</span>}
                          <span className="col-type-tag">{spec.type}</span>
                        </th>
                      ))}
                      <th className="col-actions">Revert</th>
                    </tr>
                  </thead>
                  <tbody>
                    {targetRecords.map(rec => {
                      const modified = isRowModified(rec.id);
                      return (
                        <tr key={rec.id} className={modified ? 'row-is-modified' : ''}>
                          <td className="col-sticky-id">
                            <span className="rec-id-tag">#{rec.id}</span>
                            {rec._record_label && <small className="rec-id-subtle">{rec._record_label}</small>}
                            {modified && <span className="edited-badge">Edited</span>}
                          </td>
                          {Object.entries(schema.fields).map(([name, spec]) => {
                            const cellMod = isCellModified(rec.id, name);
                            return (
                              <td key={name} className={cellMod ? 'cell-modified' : ''}>
                                <FieldControl
                                  id={`bulk-${rec.id}-${name}`}
                                  name={name}
                                  spec={spec}
                                  value={rowsData[rec.id]?.[name]}
                                  onChange={val => handleCellChange(rec.id, name, val)}
                                  compact
                                  className={cellMod ? 'input-modified' : ''}
                                />
                              </td>
                            );
                          })}
                          <td className="col-actions">
                            {modified ? (
                              <button
                                type="button"
                                className="row-reset-btn"
                                title="Reset this row to original values"
                                onClick={() => handleResetRow(rec.id)}
                              >
                                <RotateCcw size={13} />
                              </button>
                            ) : (
                              <span className="cell-unchanged muted">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="modal-footer">
            <div className="modal-footer-summary">
              {modifiedCount > 0 ? (
                <span className="bulk-count-badge">
                  <strong>{modifiedCount}</strong> of {targetRecords.length} record(s) modified
                </span>
              ) : (
                <span className="muted">No changes yet. Manually edit any necessary columns in the table above.</span>
              )}
            </div>
            <div className="modal-footer-actions">
              <button type="button" className="ghost-button" onClick={onClose} disabled={busy}>
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={busy || modifiedCount === 0 || !schema}
              >
                <Save size={16} />
                {busy ? 'Saving changes…' : `Save All Records (${modifiedCount} modified)`}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

export function DeleteConfirmModal({ table, target, onClose, onDeleted }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const isBulk = target?.type === 'bulk';
  const count = isBulk ? target.ids.length : 1;
  const record = !isBulk ? target.record : null;

  async function handleDelete() {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      let data;
      if (isBulk) {
        try {
          data = await request(`/upload/records/${table.name}/bulk`, undefined, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: target.ids }),
          });
        } catch (delErr) {
          if (delErr.message && (delErr.message.includes('Method Not Allowed') || delErr.message.includes('405'))) {
            data = await request(`/upload/records/${table.name}/delete-bulk`, undefined, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ids: target.ids }),
            });
          } else {
            throw delErr;
          }
        }
      } else {
        try {
          data = await request(`/tables/${table.name}/${record.id}`, undefined, {
            method: 'DELETE',
          });
        } catch (tableErr) {
          if (tableErr.message && (tableErr.message.includes('Method Not Allowed') || tableErr.message.includes('405'))) {
            try {
              data = await request(`/tables/${table.name}/${record.id}/delete`, undefined, {
                method: 'POST',
              });
            } catch {
              data = await request(`/upload/record/${table.name}/${record.id}`, undefined, {
                method: 'DELETE',
              });
            }
          } else {
            throw tableErr;
          }
        }
      }
      setSuccess(data.message || 'Record deleted successfully.');
      setTimeout(() => {
        onDeleted();
        onClose();
      }, 600);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-window delete-modal-window" onClick={e => e.stopPropagation()}>
        <div className="modal-header delete-modal-header">
          <div className="modal-title">
            <Trash2 size={18} className="delete-title-icon" />
            <div>
              <h3>{isBulk ? `Delete ${count} Records` : `Delete ${table.label} #${record.id}`}</h3>
              <p className="modal-subtitle">Permanent deletion confirmation.</p>
            </div>
          </div>
          <button className="modal-close-btn" aria-label="Close" onClick={onClose} disabled={busy}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body delete-modal-body">
          {success && (
            <div className="entry-success" role="status">
              <CheckCircle2 size={18} />
              <span>{success}</span>
            </div>
          )}

          <ErrorNotice title="Failed to delete record" error={error} />

          <div className="delete-warning-box">
            <AlertTriangle size={24} className="delete-warning-icon" />
            <div>
              <p className="delete-warning-text">
                {isBulk
                  ? `Are you sure you want to permanently delete ${count} selected records from "${table.label}"?`
                  : `Are you sure you want to permanently delete ${table.label} record #${record.id}${record._record_label ? ` (${record._record_label})` : ''}?`}
              </p>
              <p className="delete-warning-subtext">
                This action cannot be undone. If other database records depend on {isBulk ? 'these records' : 'this record'}, the deletion will be prevented to protect database integrity.
              </p>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="ghost-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="danger-button"
            onClick={handleDelete}
            disabled={busy || !!success}
          >
            <Trash2 size={16} />
            {busy ? 'Deleting…' : isBulk ? `Delete ${count} Records` : 'Delete Record'}
          </button>
        </div>
      </div>
    </div>
  );
}
