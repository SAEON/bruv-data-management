import { useEffect, useState, useMemo } from 'react';
import { Database, Fish, Search, RefreshCw, Table2, ChevronLeft, ChevronRight, Menu, X, Plus, Upload, Pencil, Edit2, CheckSquare, Trash2, Download, Network, Users, Layers, PanelLeftClose, PanelLeftOpen, ChevronDown } from 'lucide-react';
import { BACKEND_URL, request } from './api';
import DataEntry from './DataEntry';
import { EditRecordModal, BulkEditModal, DeleteConfirmModal } from './EditModals';
import DatabaseSchema from './DatabaseSchema';

const TABLE_ACTIONS = [
  { name: 'records', label: 'Records', icon: <Table2 size={16} /> },
  { name: 'capture', label: 'Single record', icon: <Plus size={16} /> },
  { name: 'upload', label: 'Bulk upload', icon: <Upload size={16} /> },
];

const SYSTEM_TABLES = new Set([
  'users',
  'roles',
  'user_roles',
  'agents',
  'people',
  'upload_logs',
]);

const SURVEY_TABLES_ORDER = [
  'projects',
  'fieldtrips',
  'day_sheets',
  'calibrations',
  'deployments',
  'analysis_periods',
  'observations',
  'measurements',
];

const SYSTEM_TABLES_ORDER = [
  'roles',
  'users',
  'user_roles',
  'agents',
  'people',
  'upload_logs',
];

const SURVEY_TABLE_HINTS = {
  projects: '1. Research Projects (Top-level parent)',
  fieldtrips: '2. Field Expeditions (Belongs to Project)',
  day_sheets: '3. Daily Field Logs (Maritime & field conditions per Trip)',
  calibrations: '4. Camera Calibrations (Stereo camera calibration per Trip)',
  deployments: '5. BRUV Deployments (Camera drops per Trip, uses Calibration)',
  analysis_periods: '6. Analysis Periods (Video analysis timeframe per Deployment)',
  observations: '7. Species Observations (Biodiversity counts & MaxN per Deployment)',
  measurements: '8. Fish Measurements (3D stereo length measurements per Deployment)',
};

function EntryTabs({ mode, onChange, readOnly }) {
  function navigate(event) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const buttons = [...event.currentTarget.querySelectorAll('button:not(:disabled)')];
    const index = buttons.indexOf(document.activeElement);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 :
      (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].focus(); buttons[next].click();
  }
  return <div className="entry-tabs" role="tablist" aria-label="Table actions" onKeyDown={navigate}>
    {TABLE_ACTIONS.map(({ name, label, icon }) => <button key={name} id={`tab-${name}`}
      role="tab" aria-selected={mode === name} aria-controls="table-content" tabIndex={mode === name ? 0 : -1}
      disabled={readOnly && name !== 'records'} title={readOnly && name !== 'records' ? 'Upload logs are created automatically during imports.' : undefined}
      onClick={() => onChange(name)}>{icon}{label}</button>)}
  </div>;
}

const formatCount = value => value == null ? '—' : value.toLocaleString();
function cell(value) {
  if (value == null) return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

function TableRecords({ table, revision, onSaved }) {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({ search: '', page: 0 });
  const [state, setState] = useState({ loading: true, data: null, error: '' });
  const [selected, setSelected] = useState(new Set());
  const [editingRow, setEditingRow] = useState(null);
  const [bulkEditOpen, setBulkEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    request(`/tables/${table.name}?skip=${filters.page * 50}&limit=50&search=${encodeURIComponent(filters.search)}`, controller.signal)
      .then(data => {
        setState({ loading: false, data, error: '' });
        setSelected(new Set());
      })
      .catch(error => { if (error.name !== 'AbortError') setState({ loading: false, data: null, error: error.message }); });
    return () => controller.abort();
  }, [table.name, filters, revision]);

  function changeFilters(next) { setState({ loading: true, data: null, error: '' }); setFilters(next); }
  const { loading, data, error } = state;
  const pages = Math.max(1, Math.ceil((data?.total || 0) / 50));
  const items = data?.items || [];
  const isReadOnly = table.name === 'upload_logs';
  const allOnPageSelected = items.length > 0 && items.every(r => selected.has(r.id));

  function toggleSelectAll() {
    if (allOnPageSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(items.map(r => r.id)));
    }
  }

  function toggleRow(id) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleDownload(format, ids = null) {
    const base = BACKEND_URL.replace(/[/]$/, "");
    if (ids && ids.length > 0) {
      if (ids.length <= 150) {
        const url = `${base}/tables/${table.name}/download?format=${format}&ids=${ids.join(',')}`;
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${table.name}_selected_records.${format}`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        return;
      }
      try {
        const response = await fetch(`${base}/tables/${table.name}/download`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids, format }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `${table.name}_selected_records.${format}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(downloadUrl);
      } catch (err) {
        alert(`Could not download selected records: ${err.message}`);
      }
    } else {
      const searchParam = filters.search ? `&search=${encodeURIComponent(filters.search)}` : '';
      const url = `${base}/tables/${table.name}/download?format=${format}${searchParam}`;
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${table.name}_records.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    }
  }

  const selectedIds = Array.from(selected);
  const selectedIdsParam = selectedIds.join(',');

  return <>
    <div className="table-toolbar">
      <form className="search-box" onSubmit={event => { event.preventDefault(); changeFilters({ search: query, page: 0 }); }}>
        <Search size={18} aria-hidden="true" />
        <input aria-label={`Search ${table.label}`} placeholder="Search this table…" value={query} onChange={event => setQuery(event.target.value)} />
        <button type="submit">Search</button>
      </form>
      <div className="table-toolbar-right">
        {selected.size > 0 ? (
          <div className="bulk-badge">
            <CheckSquare size={14} />
            <span>{selected.size} selected</span>
            {!isReadOnly && (
              <>
                <button type="button" className="primary-button compact" onClick={() => setBulkEditOpen(true)}>
                  <Edit2 size={13} /> Bulk edit ({selected.size})
                </button>
                <button
                  type="button"
                  className="danger-button compact"
                  title="Delete selected records"
                  onClick={() => setDeleteTarget({ type: 'bulk', ids: selectedIds })}
                >
                  <Trash2 size={13} /> Delete ({selected.size})
                </button>
              </>
            )}
            <button
              type="button"
              className="ghost-button compact download-badge-btn"
              title={`Download ${selected.size} selected records as CSV`}
              onClick={() => handleDownload('csv', selectedIds)}
            >
              <Download size={13} /> CSV
            </button>
            <button
              type="button"
              className="ghost-button compact download-badge-btn"
              title={`Download ${selected.size} selected records as Excel`}
              onClick={() => handleDownload('xlsx', selectedIds)}
            >
              <Download size={13} /> Excel
            </button>
            <button type="button" className="ghost-button compact" onClick={() => setSelected(new Set())}>
              Clear
            </button>
          </div>
        ) : (
          items.length > 0 && !isReadOnly && (
            <button
              type="button"
              className="ghost-button compact bulk-edit-page-trigger"
              title="Bulk edit all displayed records"
              onClick={() => setBulkEditOpen(true)}
            >
              <Edit2 size={13} /> Bulk edit ({items.length})
            </button>
          )
        )}
        <div className="download-records-group" title="Download records">
          {selected.size > 0 ? (
            <>
              <a
                href={`${BACKEND_URL.replace(/[/]$/, "")}/tables/${table.name}/download?format=csv&ids=${selectedIdsParam}`}
                className="ghost-button compact download-records-btn highlight"
                title={`Download ${selected.size} selected records as CSV`}
                download={`${table.name}_selected_records.csv`}
                onClick={(e) => {
                  if (selected.size > 150) {
                    e.preventDefault();
                    handleDownload('csv', selectedIds);
                  }
                }}
              >
                <Download size={13} />
                <span>Download CSV ({selected.size} selected)</span>
              </a>
              <a
                href={`${BACKEND_URL.replace(/[/]$/, "")}/tables/${table.name}/download?format=xlsx&ids=${selectedIdsParam}`}
                className="ghost-button compact download-records-btn highlight"
                title={`Download ${selected.size} selected records as Excel`}
                download={`${table.name}_selected_records.xlsx`}
                onClick={(e) => {
                  if (selected.size > 150) {
                    e.preventDefault();
                    handleDownload('xlsx', selectedIds);
                  }
                }}
              >
                <Download size={13} />
                <span>Download Excel ({selected.size} selected)</span>
              </a>
              <a
                href={`${BACKEND_URL.replace(/[/]$/, "")}/tables/${table.name}/download?format=csv${filters.search ? `&search=${encodeURIComponent(filters.search)}` : ''}`}
                className="ghost-button compact download-all-btn"
                title={`Download all ${formatCount(data?.total)} records as CSV`}
                download={`${table.name}_records.csv`}
              >
                <span>All records</span>
              </a>
            </>
          ) : (
            <>
              <a
                href={`${BACKEND_URL.replace(/[/]$/, "")}/tables/${table.name}/download?format=csv${filters.search ? `&search=${encodeURIComponent(filters.search)}` : ''}`}
                className="ghost-button compact download-records-btn"
                title={`Download all ${table.label} records as CSV`}
                download={`${table.name}_records.csv`}
              >
                <Download size={13} />
                <span>Download CSV</span>
              </a>
              <a
                href={`${BACKEND_URL.replace(/[/]$/, "")}/tables/${table.name}/download?format=xlsx${filters.search ? `&search=${encodeURIComponent(filters.search)}` : ''}`}
                className="ghost-button compact download-records-btn"
                title={`Download all ${table.label} records as Excel`}
                download={`${table.name}_records.xlsx`}
              >
                <Download size={13} />
                <span>Download Excel</span>
              </a>
            </>
          )}
        </div>
        <span className="muted">{loading ? 'Loading records…' : `${formatCount(data?.total)} ${filters.search ? 'matching ' : ''}records`}</span>
      </div>
    </div>
    {error ? <div className="empty-state error" role="alert">{error}<button onClick={() => changeFilters({ ...filters })}>Try again</button></div> : loading ? <div className="empty-state" role="status">Loading records…</div> : <>
      <div className="table-scroll">
        <table>
          <caption className="sr-only">{table.label} records</caption>
          <thead>
            <tr>
              <th className="th-checkbox">
                <input
                  type="checkbox"
                  aria-label="Select all on this page"
                  checked={allOnPageSelected}
                  onChange={toggleSelectAll}
                />
              </th>
              {data.columns.map(column => <th key={column.name} scope="col">{column.label}</th>)}
              {!isReadOnly && <th scope="col" className="th-actions">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {items.map((row, index) => {
              const isChecked = selected.has(row.id);
              return (
                <tr key={row.id ?? index} className={isChecked ? 'row-selected' : ''}>
                  <td className="td-checkbox">
                    <input
                      type="checkbox"
                      aria-label={`Select record #${row.id}`}
                      checked={isChecked}
                      onChange={() => toggleRow(row.id)}
                    />
                  </td>
                  {data.columns.map(column => {
                    const val = row[column.name];
                    const isIdColumn = column.name === 'id' || column.is_primary_key;
                    const fkName = row._display_names?.[column.name];
                    const pkName = row._record_label && row._record_label !== `#${val}`
                      ? row._record_label
                      : null;

                    if (isIdColumn) {
                      return (
                        <td key={column.name} title={pkName ? `${pkName} (ID: ${val})` : `ID: ${val}`}>
                          <span className="cell-id">{val != null ? val : '—'}</span>
                        </td>
                      );
                    }

                    if (fkName) {
                      return (
                        <td key={column.name} title={`ID: ${val}`}>
                          <span className="cell-entity-name fk-name">{fkName}</span>
                        </td>
                      );
                    }

                    return (
                      <td key={column.name} title={cell(val)}>
                        {cell(val)}
                      </td>
                    );
                  })}
                  {!isReadOnly && (
                    <td className="td-actions">
                      <div className="row-actions-group">
                        <button
                          type="button"
                          className="row-edit-button"
                          title={`Edit ${table.label}: #${row.id}`}
                          onClick={() => setEditingRow(row)}
                        >
                          <Pencil size={12} />
                          <span>Edit</span>
                        </button>
                        <button
                          type="button"
                          className="row-delete-button"
                          title={`Delete ${table.label}: #${row.id}`}
                          onClick={() => setDeleteTarget({ type: 'single', record: row })}
                        >
                          <Trash2 size={12} />
                          <span>Delete</span>
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {items.length === 0 && <div className="empty-state"><Table2 size={32} /><h3>{filters.search ? 'No matching records' : 'No records yet'}</h3><p>{filters.search ? 'Try a different search.' : 'This table is ready for data.'}</p></div>}
      </div>
      <div className="pagination">
        <span>{data.total ? `${filters.page * 50 + 1}–${Math.min((filters.page + 1) * 50, data.total)} of ${formatCount(data.total)}` : '0 records'}</span>
        <div>
          <button aria-label="Previous page" disabled={filters.page === 0} onClick={() => changeFilters({ ...filters, page: filters.page - 1 })}><ChevronLeft size={16} /></button>
          <span>Page {filters.page + 1} of {pages}</span>
          <button aria-label="Next page" disabled={filters.page + 1 >= pages} onClick={() => changeFilters({ ...filters, page: filters.page + 1 })}><ChevronRight size={16} /></button>
        </div>
      </div>
    </>}

    {editingRow && (
      <EditRecordModal
        table={table}
        record={editingRow}
        onClose={() => setEditingRow(null)}
        onSaved={onSaved}
      />
    )}

    {bulkEditOpen && (
      <BulkEditModal
        table={table}
        records={selected.size > 0 ? items.filter(r => selected.has(r.id)) : items}
        selectedIds={selectedIds}
        onClose={() => setBulkEditOpen(false)}
        onSaved={() => {
          setSelected(new Set());
          onSaved();
        }}
      />
    )}

    {deleteTarget && (
      <DeleteConfirmModal
        table={table}
        target={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={() => {
          setSelected(new Set());
          onSaved();
        }}
      />
    )}
  </>;
}

export default function App() {
  const [view, setView] = useState('tables'); // 'tables' | 'schema'
  const [catalog, setCatalog] = useState({ loading: true, tables: [], error: '' });
  const [selected, setSelected] = useState('projects');
  const [revision, setRevision] = useState(0);
  const [tableQuery, setTableQuery] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('bruv_sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });
  const [surveyExpanded, setSurveyExpanded] = useState(true);
  const [systemExpanded, setSystemExpanded] = useState(true);
  const [mode, setMode] = useState('records');

  useEffect(() => {
    try {
      localStorage.setItem('bruv_sidebar_collapsed', String(sidebarCollapsed));
    } catch {
      // localStorage might be unavailable
    }
  }, [sidebarCollapsed]);

  useEffect(() => {
    function handleKeyDown(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'b') {
        event.preventDefault();
        if (window.innerWidth <= 720) {
          setSidebarOpen(previous => !previous);
        } else {
          setSidebarCollapsed(previous => !previous);
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    request('/tables/', controller.signal).then(data => setCatalog({ loading: false, tables: data.tables, error: '' }))
      .catch(error => { if (error.name !== 'AbortError') setCatalog(previous => ({ ...previous, loading: false, error: error.message })); });
    return () => controller.abort();
  }, [revision]);
  const filteredSurveyTables = useMemo(() => {
    return catalog.tables
      .filter(table => !SYSTEM_TABLES.has(table.name))
      .filter(table => `${table.label} ${table.name}`.toLowerCase().includes(tableQuery.toLowerCase()))
      .sort((a, b) => {
        const indexA = SURVEY_TABLES_ORDER.indexOf(a.name);
        const indexB = SURVEY_TABLES_ORDER.indexOf(b.name);
        if (indexA !== -1 && indexB !== -1) return indexA - indexB;
        if (indexA !== -1) return -1;
        if (indexB !== -1) return 1;
        return a.label.localeCompare(b.label);
      });
  }, [catalog.tables, tableQuery]);

  const filteredSystemTables = useMemo(() => {
    return catalog.tables
      .filter(table => SYSTEM_TABLES.has(table.name))
      .filter(table => `${table.label} ${table.name}`.toLowerCase().includes(tableQuery.toLowerCase()))
      .sort((a, b) => {
        const indexA = SYSTEM_TABLES_ORDER.indexOf(a.name);
        const indexB = SYSTEM_TABLES_ORDER.indexOf(b.name);
        if (indexA !== -1 && indexB !== -1) return indexA - indexB;
        if (indexA !== -1) return -1;
        if (indexB !== -1) return 1;
        return a.label.localeCompare(b.label);
      });
  }, [catalog.tables, tableQuery]);

  const isSurveyOpen = surveyExpanded || tableQuery.trim() !== '';
  const isSystemOpen = systemExpanded || tableQuery.trim() !== '';
  const allGroupsExpanded = isSurveyOpen && isSystemOpen;

  const active = catalog.tables.find(table => table.name === selected) || catalog.tables[0];
  function refresh() { setCatalog(previous => ({ ...previous, loading: true, error: '' })); setRevision(value => value + 1); }
  return <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    {sidebarOpen && <button className="sidebar-backdrop" aria-label="Close table navigation" onClick={() => setSidebarOpen(false)} />}
    <aside className={`sidebar ${sidebarOpen ? 'is-open' : ''} ${sidebarCollapsed ? 'is-collapsed' : ''}`}>
      <div className="brand">
        <span className="brand-mark"><Fish size={25} /></span>
        <div className="brand-title"><strong>Marine</strong><span>Data management</span></div>
        <button
          type="button"
          className="sidebar-collapse-btn desktop-only"
          aria-label="Collapse navigation bar"
          title="Collapse navigation bar (Ctrl+B)"
          onClick={() => setSidebarCollapsed(true)}
        >
          <PanelLeftClose size={18} />
        </button>
        <button
          type="button"
          className="mobile-close"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        >
          <X size={20} />
        </button>
      </div>

      <div className="sidebar-view-nav">
        <button
          type="button"
          className={`view-nav-btn ${view === 'tables' ? 'active' : ''}`}
          onClick={() => { setView('tables'); setSidebarOpen(false); }}
        >
          <Table2 size={16} />
          <span>Table Browser</span>
        </button>
      </div>

      <div className="sidebar-label">
        <span>TABLES</span>
        <div className="sidebar-label-actions">
          {catalog.tables.length > 0 && !catalog.loading && (
            <button
              type="button"
              className="sidebar-collapse-all-btn"
              onClick={() => {
                const nextState = !allGroupsExpanded;
                setSurveyExpanded(nextState);
                setSystemExpanded(nextState);
              }}
              title={allGroupsExpanded ? "Collapse all table groups" : "Expand all table groups"}
            >
              {allGroupsExpanded ? 'Collapse' : 'Expand'}
            </button>
          )}
          <span className="sidebar-tables-total">{catalog.tables.length}</span>
        </div>
      </div>
      <label className="table-filter"><Search size={16} /><input aria-label="Filter tables" placeholder="Find a table…" value={tableQuery} onChange={event => setTableQuery(event.target.value)} /></label>
      <nav className="table-nav" aria-label="Database tables">
        {filteredSurveyTables.length > 0 && (
          <div className="nav-group">
            <button
              type="button"
              className="nav-group-header"
              onClick={() => setSurveyExpanded(previous => !previous)}
              aria-expanded={isSurveyOpen}
              aria-controls="survey-tables-group"
              title={isSurveyOpen ? "Collapse Survey Data" : "Expand Survey Data"}
            >
              <span>
                <ChevronDown size={13} className={`group-chevron ${isSurveyOpen ? 'is-open' : 'is-collapsed'}`} />
                <Layers size={13} />
                Survey Data
              </span>
              <span className="nav-group-count">{filteredSurveyTables.length}</span>
            </button>
            {isSurveyOpen && (
              <div id="survey-tables-group" className="nav-group-items">
                {filteredSurveyTables.map(table => (
                  <button
                    key={table.name}
                    className={active?.name === table.name && view === 'tables' ? 'selected' : ''}
                    aria-current={active?.name === table.name && view === 'tables' ? 'page' : undefined}
                    title={SURVEY_TABLE_HINTS[table.name] || table.label}
                    onClick={() => {
                      setSelected(table.name);
                      setView('tables');
                      setMode('records');
                      setSidebarOpen(false);
                    }}
                  >
                    <Table2 size={17} />
                    <span>{table.label}</span>
                    <span className="count" title={table.error || `${table.count} records`}>
                      {catalog.loading ? '…' : formatCount(table.count)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {filteredSystemTables.length > 0 && (
          <div className="nav-group">
            <button
              type="button"
              className="nav-group-header"
              onClick={() => setSystemExpanded(previous => !previous)}
              aria-expanded={isSystemOpen}
              aria-controls="system-tables-group"
              title={isSystemOpen ? "Collapse Users & Systems" : "Expand Users & Systems"}
            >
              <span>
                <ChevronDown size={13} className={`group-chevron ${isSystemOpen ? 'is-open' : 'is-collapsed'}`} />
                <Users size={13} />
                Users & Systems
              </span>
              <span className="nav-group-count">{filteredSystemTables.length}</span>
            </button>
            {isSystemOpen && (
              <div id="system-tables-group" className="nav-group-items">
                {filteredSystemTables.map(table => (
                  <button
                    key={table.name}
                    className={active?.name === table.name && view === 'tables' ? 'selected' : ''}
                    aria-current={active?.name === table.name && view === 'tables' ? 'page' : undefined}
                    onClick={() => {
                      setSelected(table.name);
                      setView('tables');
                      setMode('records');
                      setSidebarOpen(false);
                    }}
                  >
                    <Table2 size={17} />
                    <span>{table.label}</span>
                    <span className="count" title={table.error || `${table.count} records`}>
                      {catalog.loading ? '…' : formatCount(table.count)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {catalog.loading && !catalog.tables.length && (
          <p className="sidebar-message">Loading tables…</p>
        )}

        {!catalog.loading && catalog.tables.length > 0 && filteredSurveyTables.length === 0 && filteredSystemTables.length === 0 && (
          <p className="sidebar-message">No tables match.</p>
        )}
      </nav>

      <div className="sidebar-bottom-nav">
        <button
          type="button"
          className={`view-nav-btn ${view === 'schema' ? 'active' : ''}`}
          onClick={() => { setView('schema'); setSidebarOpen(false); }}
        >
          <Network size={16} />
          <span>Database ERD</span>
          <span className="view-badge">ERD</span>
        </button>
      </div>

      <div className="sidebar-footer">Marine biodiversity database</div>
    </aside>
    <div className="main-area">
      <header className="topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="sidebar-toggle-btn"
            aria-label={sidebarCollapsed ? "Expand navigation bar" : "Collapse navigation bar"}
            title={sidebarCollapsed ? "Expand navigation bar (Ctrl+B)" : "Collapse navigation bar (Ctrl+B)"}
            onClick={() => {
              if (window.innerWidth <= 720) {
                setSidebarOpen(previous => !previous);
              } else {
                setSidebarCollapsed(previous => !previous);
              }
            }}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            <span className="toggle-btn-text">{sidebarCollapsed ? 'Expand navigation' : 'Collapse'}</span>
          </button>
          <span>Workspace <span className="breadcrumb-divider">/</span> <strong>{view === 'schema' ? 'Database Schema & ER Relationships' : 'Table browser'}</strong></span>
        </div>
        <button className="refresh-button" onClick={refresh} disabled={catalog.loading}><RefreshCw size={16} />{catalog.loading ? 'Refreshing…' : 'Refresh counts'}</button>
      </header>
      <main>
        {view === 'schema' ? (
          <DatabaseSchema
            initialTable={selected}
            onSelectTableInBrowser={(tblName) => {
              setSelected(tblName);
              setView('tables');
              setMode('records');
            }}
          />
        ) : (
          <>
            <div className="page-heading">
              <div>
                <p className="eyebrow">DATABASE EXPLORER</p>
                <h1>{active?.label || 'Your tables'}</h1>
                <p className="muted">Browse, capture, and import your marine survey records.</p>
              </div>
              {active && <div className="record-summary"><span className="summary-icon"><Database size={21} /></span><div><strong>{catalog.loading ? '…' : formatCount(active.count)}</strong><span>Records in this table</span></div></div>}
            </div>
            {catalog.error && <div className="error-banner" role="alert">{catalog.error}<button onClick={refresh}>Retry</button></div>}
            {active && (
              <section className="records-panel" aria-label={`${active.label} records`}>
                <div className="panel-heading">
                  <h2><Table2 size={18} />{active.name}</h2>
                  <span className="table-tag">Table</span>
                </div>
                <EntryTabs mode={mode} onChange={setMode} readOnly={active.name === 'upload_logs'} />
                <div id="table-content" role="tabpanel" aria-labelledby={`tab-${mode}`}>
                  {mode === 'records' ? (
                    <TableRecords key={`${active.name}:${revision}`} table={active} revision={revision} onSaved={refresh} />
                  ) : (
                    <DataEntry key={active.name} table={active} mode={mode} onSaved={refresh} />
                  )}
                </div>
              </section>
            )}
            {!active && catalog.loading && <div className="empty-state" role="status">Loading database tables…</div>}
          </>
        )}
      </main>
    </div>
  </div>;
}
