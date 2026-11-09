import { useEffect, useState, useMemo, useRef, useLayoutEffect, useCallback } from 'react';
import {
  Network,
  Table2,
  Key,
  Link2,
  ArrowRight,
  ArrowLeft,
  ArrowUpRight,
  ArrowDownLeft,
  Search,
  Copy,
  Check,
  Database,
  ExternalLink,
  Layers,
  Shield,
  FileCode,
  Eye,
  Info,
  RefreshCw,
  X,
  CheckSquare,
  Square,
} from 'lucide-react';
import { request } from './api';

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

function typeBadgeClass(typeStr = '') {
  const t = typeStr.toUpperCase();
  if (t.includes('INT') || t.includes('SERIAL')) return 'type-badge-int';
  if (t.includes('CHAR') || t.includes('TEXT')) return 'type-badge-text';
  if (t.includes('BOOL')) return 'type-badge-bool';
  if (t.includes('TIME') || t.includes('DATE')) return 'type-badge-date';
  if (t.includes('FLOAT') || t.includes('NUMERIC') || t.includes('DOUBLE')) return 'type-badge-float';
  return 'type-badge-other';
}

export function SingleTableSchemaView({
  table,
  schemaData = null,
  onNavigateTable = null,
  onOpenFullDiagram = null,
  onNavigateToRecords = null,
}) {
  const [fetchState, setFetchState] = useState({ data: null, error: '' });
  const tableName = table?.name || table;

  useEffect(() => {
    if (schemaData) {
      return;
    }
    const controller = new AbortController();
    request(`/tables/${tableName}/schema`, controller.signal)
      .then((res) => {
        setFetchState({ data: res, error: '' });
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setFetchState({ data: null, error: err.message || 'Unable to load table schema' });
        }
      });
    return () => controller.abort();
  }, [tableName, schemaData]);

  const data = schemaData || fetchState.data;
  const loading = !schemaData && !data && !fetchState.error;
  const error = fetchState.error;

  if (loading) {
    return (
      <div className="empty-state" role="status">
        <RefreshCw size={24} className="spin" />
        <p>Loading schema for {tableName}…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="entry-error" role="alert">
        <p>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const {
    name,
    label,
    row_count,
    columns = [],
    primary_keys = [],
    foreign_keys = [],
    outgoing_relationships = [],
    incoming_relationships = [],
    indexes = [],
    unique_constraints = [],
  } = data;

  return (
    <div className="single-table-schema">
      <div className="schema-table-header">
        <div className="schema-header-info">
          <div className="schema-header-title">
            <h3>{label}</h3>
            <span className="code-tag">{name}</span>
          </div>
          <p className="muted">
            PostgreSQL table definition with data types, constraints, and relational links.
          </p>
        </div>
        <div className="schema-header-actions">
          {onOpenFullDiagram && (
            <button
              type="button"
              className="ghost-button compact"
              onClick={() => onOpenFullDiagram(name)}
              title="View this table in the full interactive Database ER Diagram"
            >
              <Network size={14} /> View in ER Diagram
            </button>
          )}
          {onNavigateToRecords && (
            <button
              type="button"
              className="primary-button compact"
              onClick={() => onNavigateToRecords(name)}
              title="Browse records in Table Browser"
            >
              <Table2 size={14} /> Browse records
            </button>
          )}
        </div>
      </div>

      <div className="schema-stat-grid">
        <div className="schema-stat-card">
          <span className="stat-label">Columns</span>
          <strong>{columns.length}</strong>
        </div>
        <div className="schema-stat-card">
          <span className="stat-label">Primary Key</span>
          <strong>{primary_keys.join(', ') || 'None'}</strong>
        </div>
        <div className="schema-stat-card">
          <span className="stat-label">Foreign Keys</span>
          <strong>{foreign_keys.length}</strong>
        </div>
        <div className="schema-stat-card">
          <span className="stat-label">Referenced By</span>
          <strong>{incoming_relationships.length} tables</strong>
        </div>
        <div className="schema-stat-card">
          <span className="stat-label">Row Count</span>
          <strong>{row_count != null ? row_count.toLocaleString() : '—'}</strong>
        </div>
      </div>

      <div className="schema-section">
        <div className="schema-section-title">
          <h4>
            <Layers size={16} /> Columns & Data Types ({columns.length})
          </h4>
        </div>
        <div className="table-scroll">
          <table className="schema-columns-table">
            <thead>
              <tr>
                <th scope="col">Column</th>
                <th scope="col">Friendly Label</th>
                <th scope="col">Data Type</th>
                <th scope="col">Attributes</th>
                <th scope="col">Default Value</th>
                <th scope="col">Foreign Key Reference</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col) => {
                const isPk = col.is_primary_key;
                const isFk = col.is_foreign_key;
                return (
                  <tr key={col.name} className={isPk ? 'row-pk' : isFk ? 'row-fk' : ''}>
                    <td className="cell-col-name">
                      <div className="col-name-wrapper">
                        {isPk && <span className="key-badge pk" title="Primary Key"><Key size={11} /> PK</span>}
                        {isFk && <span className="key-badge fk" title="Foreign Key"><Link2 size={11} /> FK</span>}
                        <code>{col.name}</code>
                      </div>
                    </td>
                    <td className="cell-col-label">{col.label}</td>
                    <td>
                      <span className={`type-badge ${typeBadgeClass(col.type)}`}>
                        {col.type}
                      </span>
                    </td>
                    <td>
                      <span className={col.nullable ? 'null-badge nullable' : 'null-badge not-null'}>
                        {col.nullable ? 'NULL' : 'NOT NULL'}
                      </span>
                    </td>
                    <td className="cell-default">
                      {col.default ? <code>{col.default}</code> : <span className="muted">—</span>}
                    </td>
                    <td className="cell-fk-target">
                      {col.foreign_key ? (
                        <div className="fk-target-link">
                          <ArrowRight size={13} className="text-muted" />
                          {onNavigateTable ? (
                            <button
                              type="button"
                              className="link-button"
                              onClick={() => onNavigateTable(col.foreign_key.target_table)}
                              title={`Jump to ${col.foreign_key.target_table}`}
                            >
                              <strong>{col.foreign_key.target_table}</strong>.{col.foreign_key.target_column}
                            </button>
                          ) : (
                            <span>
                              <strong>{col.foreign_key.target_table}</strong>.{col.foreign_key.target_column}
                            </span>
                          )}
                          <span className="muted">({col.foreign_key.target_label})</span>
                        </div>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="schema-rel-grid">
        <div className="schema-card">
          <div className="schema-card-header">
            <h4>
              <Link2 size={15} /> Outgoing References ({outgoing_relationships.length})
            </h4>
            <span className="muted text-xs">Foreign keys from this table</span>
          </div>
          <div className="schema-card-body">
            {outgoing_relationships.length === 0 ? (
              <p className="muted text-sm">This table has no foreign keys referencing other tables.</p>
            ) : (
              <ul className="rel-list">
                {outgoing_relationships.map((rel, idx) => (
                  <li key={idx} className="rel-item">
                    <div className="rel-source">
                      <code>{rel.column}</code>
                    </div>
                    <ArrowRight size={14} className="rel-arrow" />
                    <div className="rel-target">
                      {onNavigateTable ? (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => onNavigateTable(rel.target_table)}
                        >
                          <strong>{rel.target_table}</strong>.{rel.target_column}
                        </button>
                      ) : (
                        <span>
                          <strong>{rel.target_table}</strong>.{rel.target_column}
                        </span>
                      )}
                      <span className="muted text-xs">({rel.target_label})</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="schema-card">
          <div className="schema-card-header">
            <h4>
              <ArrowLeft size={15} /> Incoming References ({incoming_relationships.length})
            </h4>
            <span className="muted text-xs">Tables that link to this table</span>
          </div>
          <div className="schema-card-body">
            {incoming_relationships.length === 0 ? (
              <p className="muted text-sm">No other application tables currently reference this table.</p>
            ) : (
              <ul className="rel-list">
                {incoming_relationships.map((rel, idx) => (
                  <li key={idx} className="rel-item">
                    <div className="rel-source">
                      {onNavigateTable ? (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => onNavigateTable(rel.source_table)}
                        >
                          <strong>{rel.source_table}</strong>
                        </button>
                      ) : (
                        <strong>{rel.source_table}</strong>
                      )}
                      <span className="muted text-xs">.{rel.source_column}</span>
                    </div>
                    <ArrowRight size={14} className="rel-arrow" />
                    <div className="rel-target">
                      <code>{rel.target_column}</code>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {(indexes.length > 0 || unique_constraints.length > 0) && (
        <div className="schema-section">
          <div className="schema-section-title">
            <h4>
              <Shield size={16} /> Indexes & Unique Constraints
            </h4>
          </div>
          <div className="constraints-grid">
            {unique_constraints.map((uq, idx) => (
              <div key={idx} className="constraint-badge">
                <span className="constraint-type">UNIQUE</span>
                <strong>{uq.name || 'Unnamed constraint'}</strong>
                <span className="muted">({uq.columns?.join(', ')})</span>
              </div>
            ))}
            {indexes.map((idxItem, idx) => (
              <div key={idx} className="constraint-badge">
                <span className="constraint-type">{idxItem.unique ? 'UNIQUE INDEX' : 'INDEX'}</span>
                <strong>{idxItem.name}</strong>
                <span className="muted">({idxItem.columns?.join(', ')})</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function generateMermaidErd(tables = [], edges = []) {
  const lines = ['erDiagram'];
  tables.forEach((t) => {
    lines.push(`    ${t.name} {`);
    t.columns.forEach((c) => {
      const typeClean = c.type.replace(/\(.*?\)/g, '').replace(/\s+/g, '_').toLowerCase();
      const keyMarker = c.is_primary_key ? 'PK' : c.is_foreign_key ? 'FK' : '';
      lines.push(`        ${typeClean} ${c.name} ${keyMarker}`.trimEnd());
    });
    lines.push('    }');
  });
  edges.forEach((e) => {
    lines.push(`    ${e.target} ||--o{ ${e.source} : "references"`);
  });
  return lines.join('\n');
}

function generateSqlDdl(tables = []) {
  return tables
    .map((t) => {
      const colDefs = t.columns.map((c) => {
        let def = `    ${c.name} ${c.type}`;
        if (!c.nullable) def += ' NOT NULL';
        if (c.default) def += ` DEFAULT ${c.default}`;
        if (c.is_primary_key) def += ' PRIMARY KEY';
        return def;
      });
      t.foreign_keys?.forEach((fk) => {
        if (fk.target_table && fk.target_column) {
          colDefs.push(`    FOREIGN KEY (${fk.column || fk.constrained_columns?.[0] || 'id'}) REFERENCES ${fk.target_table}(${fk.target_column})`);
        }
      });
      return `CREATE TABLE ${t.name} (\n${colDefs.join(',\n')}\n);`;
    })
    .join('\n\n');
}

function computeErdCurves(tables, edges, cardPositions) {
  const incomingMap = {};
  const outgoingMap = {};

  edges.forEach((edge) => {
    if (!incomingMap[edge.target]) incomingMap[edge.target] = [];
    incomingMap[edge.target].push(edge.id);

    if (!outgoingMap[edge.source]) outgoingMap[edge.source] = [];
    outgoingMap[edge.source].push(edge.id);
  });

  return edges.map((edge) => {
    const s = cardPositions[edge.source];
    const t = cardPositions[edge.target];
    if (!s || !t) return null;

    const outList = outgoingMap[edge.source] || [];
    const outIdx = outList.indexOf(edge.id);
    const outFraction = (outIdx + 1) / (outList.length + 1);

    const inList = incomingMap[edge.target] || [];
    const inIdx = inList.indexOf(edge.id);
    const inFraction = (inIdx + 1) / (inList.length + 1);

    let x1, y1, x2, y2, cx1, cy1, cx2, cy2;

    if (s.top >= t.bottom - 12) {
      // Child (source) is below Parent (target)
      x1 = s.left + s.width * outFraction;
      y1 = s.top;
      x2 = t.left + t.width * inFraction;
      y2 = t.bottom;

      const dy = Math.max(35, (y1 - y2) * 0.45);
      cx1 = x1;
      cy1 = y1 - dy;
      cx2 = x2;
      cy2 = y2 + dy;
    } else if (t.top >= s.bottom - 12) {
      // Child is above Parent
      x1 = s.left + s.width * outFraction;
      y1 = s.bottom;
      x2 = t.left + t.width * inFraction;
      y2 = t.top;

      const dy = Math.max(35, (y2 - y1) * 0.45);
      cx1 = x1;
      cy1 = y1 + dy;
      cx2 = x2;
      cy2 = y2 - dy;
    } else if (s.left >= t.right - 12) {
      // Child is to the right of Parent
      x1 = s.left;
      y1 = s.top + s.height * outFraction;
      x2 = t.right;
      y2 = t.top + t.height * inFraction;

      const dx = Math.max(35, (x1 - x2) * 0.45);
      cx1 = x1 - dx;
      cy1 = y1;
      cx2 = x2 + dx;
      cy2 = y2;
    } else {
      // Child is to the left of Parent
      x1 = s.right;
      y1 = s.top + s.height * outFraction;
      x2 = t.left;
      y2 = t.top + t.height * inFraction;

      const dx = Math.max(35, (x2 - x1) * 0.45);
      cx1 = x1 + dx;
      cy1 = y1;
      cx2 = x2 - dx;
      cy2 = y2;
    }

    const d = `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;

    return {
      edge,
      d,
      midX,
      midY,
      x1,
      y1,
      x2,
      y2,
    };
  }).filter(Boolean);
}

function ErdTableCard({
  table,
  isSelected,
  isHovered,
  isDimmed,
  isParentOfSelected,
  isChildOfSelected,
  showAllColumns,
  onSelect,
  onHover,
  onLeave,
  onSelectEdge,
  onInspect,
  onBrowse,
  cardRef,
}) {
  const [expanded, setExpanded] = useState(false);
  const isCardExpanded = showAllColumns || expanded;

  const pks = table.columns.filter((c) => c.is_primary_key);
  const fks = table.columns.filter((c) => c.is_foreign_key);
  const others = table.columns.filter((c) => !c.is_primary_key && !c.is_foreign_key);

  const displayedCols = isCardExpanded
    ? [...pks, ...fks, ...others]
    : [...pks, ...fks, ...others.slice(0, Math.max(1, 6 - pks.length - fks.length))];

  const hiddenCount = table.columns.length - displayedCols.length;
  const hasIncoming = (table.incoming_relationships?.length || 0) > 0;
  const hasOutgoing = (table.outgoing_relationships?.length || 0) > 0;

  return (
    <div
      ref={cardRef}
      className={`erd-table-card ${isSelected ? 'is-selected' : ''} ${isHovered ? 'is-hovered' : ''} ${isParentOfSelected ? 'is-connected-parent' : ''} ${isChildOfSelected ? 'is-connected-child' : ''} ${isDimmed ? 'is-dimmed' : ''}`}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(table.name);
      }}
      onMouseEnter={() => onHover(table.name)}
      onMouseLeave={() => onLeave(table.name)}
    >
      <span className={`erd-port port-top ${hasIncoming && (isSelected || isParentOfSelected) ? 'is-active' : ''}`} />
      <span className={`erd-port port-bottom ${hasOutgoing && (isSelected || isChildOfSelected) ? 'is-active' : ''}`} />
      <span className={`erd-port port-left ${hasIncoming && (isSelected || isParentOfSelected) ? 'is-active' : ''}`} />
      <span className={`erd-port port-right ${hasOutgoing && (isSelected || isChildOfSelected) ? 'is-active' : ''}`} />

      <div className="erd-card-header">
        <div className="erd-card-title">
          <strong>{table.label}</strong>
          <code>{table.name}</code>
        </div>
        <div className="erd-header-badges">
          <span className="erd-conn-chip" title="Incoming and Outgoing relations">
            <Link2 size={10} />
            {table.incoming_relationships?.length || 0} in · {table.outgoing_relationships?.length || 0} out
          </span>
          <span className="erd-row-count">{table.row_count != null ? `${table.row_count} rows` : ''}</span>
        </div>
      </div>

      <div className="erd-card-body">
        {displayedCols.map((col) => (
          <div key={col.name} className="erd-card-col">
            <span className="erd-col-name">
              {col.is_primary_key && <Key size={10} className="pk-icon" title="Primary Key" />}
              {col.is_foreign_key && <Link2 size={10} className="fk-icon" title="Foreign Key" />}
              {col.name}
            </span>
            {col.foreign_key && (
              <span
                className="erd-fk-target-pill"
                title={`References ${col.foreign_key.target_table}.${col.foreign_key.target_column}`}
                onClick={(e) => {
                  e.stopPropagation();
                  if (onSelectEdge) {
                    onSelectEdge({
                      id: `${table.name}.${col.name}->${col.foreign_key.target_table}.${col.foreign_key.target_column}`,
                      source: table.name,
                      source_column: col.name,
                      target: col.foreign_key.target_table,
                      target_column: col.foreign_key.target_column,
                    });
                  }
                }}
              >
                ➔ {col.foreign_key.target_table}
              </span>
            )}
            <span className="erd-col-type">{col.type}</span>
          </div>
        ))}

        {!isCardExpanded && hiddenCount > 0 && (
          <div
            className="erd-more-cols"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(true);
            }}
          >
            +{hiddenCount} more columns
          </div>
        )}
      </div>

      <div className="erd-card-footer">
        <span>{table.columns.length} columns</span>
        <div style={{ display: 'flex', gap: '8px' }}>
          {onBrowse && (
            <span
              className="inspect-link"
              onClick={(e) => {
                e.stopPropagation();
                onBrowse(table.name);
              }}
              title="Browse table records"
            >
              Browse
            </span>
          )}
          <span
            className="inspect-link"
            onClick={(e) => {
              e.stopPropagation();
              onInspect(table.name);
            }}
            title="Inspect schema details"
          >
            Inspect <ArrowRight size={11} />
          </span>
        </div>
      </div>
    </div>
  );
}

function ErdDiagramCanvas({
  tables = [],
  edges = [],
  selectedTable = null,
  onSelectTable,
  onInspectTable,
  onBrowseRecords,
  filterDomain = 'all',
  copyToClipboard,
  copiedType,
}) {
  const [viewMode, setViewMode] = useState('canvas'); // 'canvas' | 'matrix' | 'mermaid'
  const [showRelationLabels, setShowRelationLabels] = useState(true);
  const [showAllColumns, setShowAllColumns] = useState(false);
  const [hoveredTable, setHoveredTable] = useState(null);
  const [activeEdge, setActiveEdge] = useState(null);
  const [hoveredEdge, setHoveredEdge] = useState(null);
  const [cardPositions, setCardPositions] = useState({});
  const [svgSize, setSvgSize] = useState({ width: 1200, height: 900 });

  const canvasRef = useRef(null);
  const cardRefs = useRef({});

  const bruvTables = useMemo(
    () => new Set(['projects', 'fieldtrips', 'deployments', 'observations', 'measurements', 'calibrations', 'day_sheets', 'analysis_periods']),
    []
  );

  const authTables = useMemo(
    () => new Set(['users', 'roles', 'user_roles', 'agents', 'people', 'upload_logs']),
    []
  );

  const currentTable = useMemo(() => {
    return tables.find((t) => t.name === selectedTable) || null;
  }, [tables, selectedTable]);

  const focusTable = hoveredTable || selectedTable;
  const connectedParentTables = useMemo(() => {
    if (!focusTable) return new Set();
    const set = new Set();
    edges.forEach((e) => {
      if (e.source === focusTable) set.add(e.target);
    });
    return set;
  }, [focusTable, edges]);

  const connectedChildTables = useMemo(() => {
    if (!focusTable) return new Set();
    const set = new Set();
    edges.forEach((e) => {
      if (e.target === focusTable) set.add(e.source);
    });
    return set;
  }, [focusTable, edges]);

  const updateLayout = useCallback(() => {
    if (!canvasRef.current) return;
    const container = canvasRef.current;
    const cRect = container.getBoundingClientRect();
    const positions = {};

    Object.entries(cardRefs.current).forEach(([name, el]) => {
      if (!el) return;
      const r = el.getBoundingClientRect();
      positions[name] = {
        left: r.left - cRect.left + container.scrollLeft,
        top: r.top - cRect.top + container.scrollTop,
        right: r.right - cRect.left + container.scrollLeft,
        bottom: r.bottom - cRect.top + container.scrollTop,
        width: r.width,
        height: r.height,
        centerX: (r.left + r.right) / 2 - cRect.left + container.scrollLeft,
        centerY: (r.top + r.bottom) / 2 - cRect.top + container.scrollTop,
      };
    });

    setCardPositions(positions);
    setSvgSize({
      width: Math.max(container.scrollWidth, 1200),
      height: Math.max(container.scrollHeight, 800),
    });
  }, []);

  useLayoutEffect(() => {
    updateLayout();
    const handleResize = () => updateLayout();
    window.addEventListener('resize', handleResize);

    let observer = null;
    if (canvasRef.current && typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(() => {
        updateLayout();
      });
      observer.observe(canvasRef.current);
    }

    const timer = setTimeout(updateLayout, 100);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (observer) observer.disconnect();
      clearTimeout(timer);
    };
  }, [updateLayout, tables, edges, filterDomain, showAllColumns, viewMode]);

  const curves = useMemo(() => {
    return computeErdCurves(tables, edges, cardPositions);
  }, [tables, edges, cardPositions]);

  const visibleCurves = useMemo(() => {
    return curves.filter((c) => {
      if (filterDomain === 'bruv') return bruvTables.has(c.edge.source) && bruvTables.has(c.edge.target);
      if (filterDomain === 'auth') return authTables.has(c.edge.source) && authTables.has(c.edge.target);
      return true;
    });
  }, [curves, filterDomain, bruvTables, authTables]);

  const mermaidText = useMemo(() => generateMermaidErd(tables, edges), [tables, edges]);

  // Tables partitioned for layout tiers
  const bruvTier1 = ['projects'];
  const bruvTier2 = ['fieldtrips'];
  const bruvTier3 = ['calibrations', 'deployments', 'day_sheets'];
  const bruvTier4 = ['observations', 'measurements', 'analysis_periods'];

  const authTier1 = ['users', 'roles'];
  const authTier2 = ['agents', 'user_roles', 'people'];
  const authTier3 = ['upload_logs'];

  const extraTables = tables
    .map((t) => t.name)
    .filter((name) => !bruvTables.has(name) && !authTables.has(name));

  const showBruvSection = filterDomain === 'all' || filterDomain === 'bruv';
  const showAuthSection = filterDomain === 'all' || filterDomain === 'auth';

  return (
    <div className="erd-view-container">
      {/* Top Toolbar */}
      <div className="erd-toolbar">
        <div className="erd-view-mode-tabs">
          <button
            type="button"
            className={`erd-view-mode-btn ${viewMode === 'canvas' ? 'active' : ''}`}
            onClick={() => setViewMode('canvas')}
          >
            <Network size={14} /> Connected ERD Diagram
          </button>
          <button
            type="button"
            className={`erd-view-mode-btn ${viewMode === 'matrix' ? 'active' : ''}`}
            onClick={() => setViewMode('matrix')}
          >
            <Table2 size={14} /> Relations Matrix ({edges.length})
          </button>
          <button
            type="button"
            className={`erd-view-mode-btn ${viewMode === 'mermaid' ? 'active' : ''}`}
            onClick={() => setViewMode('mermaid')}
          >
            <FileCode size={14} /> Mermaid Code
          </button>
        </div>

        <div className="erd-toolbar-controls">
          {viewMode === 'canvas' && (
            <>
              <label className="erd-toggle-option">
                <input
                  type="checkbox"
                  checked={showRelationLabels}
                  onChange={(e) => setShowRelationLabels(e.target.checked)}
                />
                <span>Relation Labels</span>
              </label>
              <label className="erd-toggle-option">
                <input
                  type="checkbox"
                  checked={showAllColumns}
                  onChange={(e) => setShowAllColumns(e.target.checked)}
                />
                <span>All Columns</span>
              </label>
            </>
          )}

          <div className="erd-legend">
            <div className="legend-item">
              <span className="key-badge pk"><Key size={10} /> PK</span>
              <span>Primary Key</span>
            </div>
            <div className="legend-item">
              <span className="key-badge fk"><Link2 size={10} /> FK</span>
              <span>Foreign Key</span>
            </div>
            <div className="legend-item">
              <span className="legend-line" />
              <span>1:N Relational Link</span>
            </div>
          </div>
        </div>
      </div>

      {/* Active Table or Edge Bar */}
      {(currentTable || activeEdge || hoveredEdge) && (
        <div className="erd-active-bar">
          <div className="erd-active-bar-content">
            {activeEdge || hoveredEdge ? (
              <>
                <span className="erd-bar-badge">Relation</span>
                <strong>{(activeEdge || hoveredEdge).source}.{(activeEdge || hoveredEdge).source_column}</strong>
                <ArrowRight size={13} className="text-teal" />
                <strong>{(activeEdge || hoveredEdge).target}.{(activeEdge || hoveredEdge).target_column}</strong>
                <span className="erd-cardinality-badge">1:N (Many-to-One)</span>
              </>
            ) : currentTable ? (
              <>
                <span className="erd-bar-badge">Focused Table</span>
                <strong>{currentTable.label}</strong>
                <code>({currentTable.name})</code>
                <span className="erd-cardinality-badge">
                  {currentTable.incoming_relationships?.length || 0} incoming · {currentTable.outgoing_relationships?.length || 0} outgoing FK(s)
                </span>
              </>
            ) : null}
          </div>
          <div className="erd-active-bar-actions">
            {activeEdge && (
              <>
                <button
                  type="button"
                  className="ghost-button compact"
                  onClick={() => onSelectTable(activeEdge.source)}
                >
                  Focus {activeEdge.source}
                </button>
                <button
                  type="button"
                  className="ghost-button compact"
                  onClick={() => onSelectTable(activeEdge.target)}
                >
                  Focus {activeEdge.target}
                </button>
                <button
                  type="button"
                  className="ghost-button compact"
                  onClick={() => setActiveEdge(null)}
                >
                  <X size={13} /> Clear
                </button>
              </>
            )}
            {!activeEdge && currentTable && (
              <>
                <button
                  type="button"
                  className="primary-button compact"
                  onClick={() => onInspectTable(currentTable.name)}
                >
                  <Table2 size={13} /> Inspect Schema
                </button>
                {onBrowseRecords && (
                  <button
                    type="button"
                    className="ghost-button compact"
                    onClick={() => onBrowseRecords(currentTable.name)}
                  >
                    <ExternalLink size={13} /> Browse Records
                  </button>
                )}
                <button
                  type="button"
                  className="ghost-button compact"
                  onClick={() => onSelectTable(null)}
                >
                  <X size={13} /> Clear Focus
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Main View: Connected Canvas */}
      {viewMode === 'canvas' && (
        <div className="erd-canvas-viewport" ref={canvasRef}>
          <div className="erd-canvas-inner">
            {/* SVG Relationship Layer */}
            <svg
              className="erd-connections-svg"
              width={svgSize.width}
              height={svgSize.height}
            >
              <defs>
                <marker
                  id="erd-arrow-default"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto"
                >
                  <path d="M 0 1 L 9 5 L 0 9 z" fill="#94a3b8" />
                </marker>
                <marker
                  id="erd-arrow-active"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="8"
                  markerHeight="8"
                  orient="auto"
                >
                  <path d="M 0 1 L 9 5 L 0 9 z" fill="#0d9488" />
                </marker>
                <marker
                  id="erd-arrow-focus"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="8"
                  markerHeight="8"
                  orient="auto"
                >
                  <path d="M 0 1 L 9 5 L 0 9 z" fill="#0284c7" />
                </marker>
              </defs>

              {visibleCurves.map((c) => {
                const isEdgeActive = activeEdge?.id === c.edge.id;
                const isEdgeHovered = hoveredEdge?.id === c.edge.id;
                const isSourceTableActive = selectedTable === c.edge.source;
                const isTargetTableActive = selectedTable === c.edge.target;
                const isSourceTableHovered = hoveredTable === c.edge.source;
                const isTargetTableHovered = hoveredTable === c.edge.target;
                const isRelatedToSelection =
                  isSourceTableActive || isTargetTableActive || isSourceTableHovered || isTargetTableHovered;
                const isDimmed =
                  (selectedTable || hoveredTable || activeEdge || hoveredEdge) &&
                  !isEdgeActive &&
                  !isEdgeHovered &&
                  !isRelatedToSelection;

                const markerName =
                  isEdgeActive || isEdgeHovered
                    ? 'active'
                    : isRelatedToSelection
                    ? 'focus'
                    : 'default';

                return (
                  <g key={c.edge.id}>
                    {/* Invisible Wide Hit Area for Mouse Interaction */}
                    <path
                      className="erd-edge-hit-area"
                      d={c.d}
                      onMouseEnter={() => setHoveredEdge(c.edge)}
                      onMouseLeave={() => setHoveredEdge(null)}
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveEdge(c.edge);
                      }}
                    />

                    {/* Visible Bezier Curve */}
                    <path
                      className={`erd-edge-path ${isEdgeActive || isEdgeHovered ? 'is-active' : ''} ${isRelatedToSelection ? 'is-selected-table' : ''} ${isDimmed ? 'is-dimmed' : ''}`}
                      d={c.d}
                      markerEnd={`url(#erd-arrow-${markerName})`}
                    />

                    {/* Midpoint Pill Label */}
                    {(showRelationLabels || isEdgeActive || isEdgeHovered || isRelatedToSelection) && (
                      <g
                        className={`erd-edge-badge ${isEdgeActive || isEdgeHovered ? 'is-active' : ''}`}
                        transform={`translate(${c.midX}, ${c.midY})`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveEdge(c.edge);
                        }}
                        onMouseEnter={() => setHoveredEdge(c.edge)}
                        onMouseLeave={() => setHoveredEdge(null)}
                      >
                        <rect x="-42" y="-10" width="84" height="20" />
                        <text x="0" y="0">
                          {c.edge.source_column} ➔ {c.edge.target_column}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
            </svg>

            {/* DOM Tier Layout */}
            {showBruvSection && (
              <div className="erd-domain-section">
                <div className="erd-domain-header">
                  <div>
                    <h3>BRUV Marine Observation Pipeline</h3>
                    <span className="muted">
                      Hierarchical flow: Projects ➔ Field Trips ➔ Deployments ➔ Observations & Measurements
                    </span>
                  </div>
                  <span className="erd-conn-chip">
                    8 Tables · 7 Relational Links
                  </span>
                </div>

                {/* Tier 1: Projects */}
                <div className="erd-tier-header">1. High-Level Research Container</div>
                <div className="erd-tier">
                  {bruvTier1.map((tblName) => {
                    const tbl = tables.find((t) => t.name === tblName);
                    if (!tbl) return null;
                    return (
                      <ErdTableCard
                        key={tblName}
                        table={tbl}
                        cardRef={(el) => (cardRefs.current[tblName] = el)}
                        isSelected={selectedTable === tblName}
                        isHovered={hoveredTable === tblName}
                        isParentOfSelected={connectedParentTables.has(tblName)}
                        isChildOfSelected={connectedChildTables.has(tblName)}
                        isDimmed={
                          (focusTable && focusTable !== tblName && !connectedParentTables.has(tblName) && !connectedChildTables.has(tblName)) ||
                          (activeEdge && activeEdge.source !== tblName && activeEdge.target !== tblName)
                        }
                        showAllColumns={showAllColumns}
                        onSelect={onSelectTable}
                        onHover={setHoveredTable}
                        onLeave={() => setHoveredTable(null)}
                        onSelectEdge={setActiveEdge}
                        onInspect={onInspectTable}
                        onBrowse={onBrowseRecords}
                      />
                    );
                  })}
                </div>

                {/* Tier 2: Field Trips */}
                <div className="erd-tier-header">2. Survey Expeditions & Field Trips</div>
                <div className="erd-tier">
                  {bruvTier2.map((tblName) => {
                    const tbl = tables.find((t) => t.name === tblName);
                    if (!tbl) return null;
                    return (
                      <ErdTableCard
                        key={tblName}
                        table={tbl}
                        cardRef={(el) => (cardRefs.current[tblName] = el)}
                        isSelected={selectedTable === tblName}
                        isHovered={hoveredTable === tblName}
                        isParentOfSelected={connectedParentTables.has(tblName)}
                        isChildOfSelected={connectedChildTables.has(tblName)}
                        isDimmed={
                          (focusTable && focusTable !== tblName && !connectedParentTables.has(tblName) && !connectedChildTables.has(tblName)) ||
                          (activeEdge && activeEdge.source !== tblName && activeEdge.target !== tblName)
                        }
                        showAllColumns={showAllColumns}
                        onSelect={onSelectTable}
                        onHover={setHoveredTable}
                        onLeave={() => setHoveredTable(null)}
                        onSelectEdge={setActiveEdge}
                        onInspect={onInspectTable}
                        onBrowse={onBrowseRecords}
                      />
                    );
                  })}
                </div>

                {/* Tier 3: Field Operations (Calibrations, Deployments, Day Sheets) */}
                <div className="erd-tier-header">3. Survey Operations, Deployments & Rig Calibrations</div>
                <div className="erd-tier">
                  {bruvTier3.map((tblName) => {
                    const tbl = tables.find((t) => t.name === tblName);
                    if (!tbl) return null;
                    return (
                      <ErdTableCard
                        key={tblName}
                        table={tbl}
                        cardRef={(el) => (cardRefs.current[tblName] = el)}
                        isSelected={selectedTable === tblName}
                        isHovered={hoveredTable === tblName}
                        isParentOfSelected={connectedParentTables.has(tblName)}
                        isChildOfSelected={connectedChildTables.has(tblName)}
                        isDimmed={
                          (focusTable && focusTable !== tblName && !connectedParentTables.has(tblName) && !connectedChildTables.has(tblName)) ||
                          (activeEdge && activeEdge.source !== tblName && activeEdge.target !== tblName)
                        }
                        showAllColumns={showAllColumns}
                        onSelect={onSelectTable}
                        onHover={setHoveredTable}
                        onLeave={() => setHoveredTable(null)}
                        onSelectEdge={setActiveEdge}
                        onInspect={onInspectTable}
                        onBrowse={onBrowseRecords}
                      />
                    );
                  })}
                </div>

                {/* Tier 4: Video Observations & Photogrammetry */}
                <div className="erd-tier-header">4. Biodiversity Observations, MaxN & Stereo Photogrammetry</div>
                <div className="erd-tier">
                  {bruvTier4.map((tblName) => {
                    const tbl = tables.find((t) => t.name === tblName);
                    if (!tbl) return null;
                    return (
                      <ErdTableCard
                        key={tblName}
                        table={tbl}
                        cardRef={(el) => (cardRefs.current[tblName] = el)}
                        isSelected={selectedTable === tblName}
                        isHovered={hoveredTable === tblName}
                        isParentOfSelected={connectedParentTables.has(tblName)}
                        isChildOfSelected={connectedChildTables.has(tblName)}
                        isDimmed={
                          (focusTable && focusTable !== tblName && !connectedParentTables.has(tblName) && !connectedChildTables.has(tblName)) ||
                          (activeEdge && activeEdge.source !== tblName && activeEdge.target !== tblName)
                        }
                        showAllColumns={showAllColumns}
                        onSelect={onSelectTable}
                        onHover={setHoveredTable}
                        onLeave={() => setHoveredTable(null)}
                        onSelectEdge={setActiveEdge}
                        onInspect={onInspectTable}
                        onBrowse={onBrowseRecords}
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {/* Security, Personnel & System Domain */}
            {showAuthSection && (
              <div className="erd-domain-section">
                <div className="erd-domain-header">
                  <div>
                    <h3>Users, Security Roles & Personnel Directory</h3>
                    <span className="muted">
                      Authentication, role-based authorization, agent profiles, and import telemetry
                    </span>
                  </div>
                  <span className="erd-conn-chip">
                    6 Tables · 4 Relational Links
                  </span>
                </div>

                {/* Tier 1: Users & Roles */}
                <div className="erd-tier-header">1. Principal Security Entities</div>
                <div className="erd-tier">
                  {authTier1.map((tblName) => {
                    const tbl = tables.find((t) => t.name === tblName);
                    if (!tbl) return null;
                    return (
                      <ErdTableCard
                        key={tblName}
                        table={tbl}
                        cardRef={(el) => (cardRefs.current[tblName] = el)}
                        isSelected={selectedTable === tblName}
                        isHovered={hoveredTable === tblName}
                        isParentOfSelected={connectedParentTables.has(tblName)}
                        isChildOfSelected={connectedChildTables.has(tblName)}
                        isDimmed={
                          (focusTable && focusTable !== tblName && !connectedParentTables.has(tblName) && !connectedChildTables.has(tblName)) ||
                          (activeEdge && activeEdge.source !== tblName && activeEdge.target !== tblName)
                        }
                        showAllColumns={showAllColumns}
                        onSelect={onSelectTable}
                        onHover={setHoveredTable}
                        onLeave={() => setHoveredTable(null)}
                        onSelectEdge={setActiveEdge}
                        onInspect={onInspectTable}
                        onBrowse={onBrowseRecords}
                      />
                    );
                  })}
                </div>

                {/* Tier 2: Junctions, Agents & People */}
                <div className="erd-tier-header">2. Role Assignments & Personnel Directory</div>
                <div className="erd-tier">
                  {authTier2.map((tblName) => {
                    const tbl = tables.find((t) => t.name === tblName);
                    if (!tbl) return null;
                    return (
                      <ErdTableCard
                        key={tblName}
                        table={tbl}
                        cardRef={(el) => (cardRefs.current[tblName] = el)}
                        isSelected={selectedTable === tblName}
                        isHovered={hoveredTable === tblName}
                        isParentOfSelected={connectedParentTables.has(tblName)}
                        isChildOfSelected={connectedChildTables.has(tblName)}
                        isDimmed={
                          (focusTable && focusTable !== tblName && !connectedParentTables.has(tblName) && !connectedChildTables.has(tblName)) ||
                          (activeEdge && activeEdge.source !== tblName && activeEdge.target !== tblName)
                        }
                        showAllColumns={showAllColumns}
                        onSelect={onSelectTable}
                        onHover={setHoveredTable}
                        onLeave={() => setHoveredTable(null)}
                        onSelectEdge={setActiveEdge}
                        onInspect={onInspectTable}
                        onBrowse={onBrowseRecords}
                      />
                    );
                  })}
                </div>

                {/* Tier 3: Upload Logs */}
                <div className="erd-tier-header">3. System Auditing & Import Telemetry</div>
                <div className="erd-tier">
                  {authTier3.map((tblName) => {
                    const tbl = tables.find((t) => t.name === tblName);
                    if (!tbl) return null;
                    return (
                      <ErdTableCard
                        key={tblName}
                        table={tbl}
                        cardRef={(el) => (cardRefs.current[tblName] = el)}
                        isSelected={selectedTable === tblName}
                        isHovered={hoveredTable === tblName}
                        isParentOfSelected={connectedParentTables.has(tblName)}
                        isChildOfSelected={connectedChildTables.has(tblName)}
                        isDimmed={
                          (focusTable && focusTable !== tblName && !connectedParentTables.has(tblName) && !connectedChildTables.has(tblName)) ||
                          (activeEdge && activeEdge.source !== tblName && activeEdge.target !== tblName)
                        }
                        showAllColumns={showAllColumns}
                        onSelect={onSelectTable}
                        onHover={setHoveredTable}
                        onLeave={() => setHoveredTable(null)}
                        onSelectEdge={setActiveEdge}
                        onInspect={onInspectTable}
                        onBrowse={onBrowseRecords}
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {/* Extra Tables if present */}
            {extraTables.length > 0 && (
              <div className="erd-domain-section">
                <div className="erd-domain-header">
                  <div>
                    <h3>Additional Database Tables</h3>
                    <span className="muted">Newly discovered or custom application tables</span>
                  </div>
                </div>
                <div className="erd-tier">
                  {extraTables.map((tblName) => {
                    const tbl = tables.find((t) => t.name === tblName);
                    if (!tbl) return null;
                    return (
                      <ErdTableCard
                        key={tblName}
                        table={tbl}
                        cardRef={(el) => (cardRefs.current[tblName] = el)}
                        isSelected={selectedTable === tblName}
                        isHovered={hoveredTable === tblName}
                        isParentOfSelected={connectedParentTables.has(tblName)}
                        isChildOfSelected={connectedChildTables.has(tblName)}
                        isDimmed={
                          (focusTable && focusTable !== tblName && !connectedParentTables.has(tblName) && !connectedChildTables.has(tblName)) ||
                          (activeEdge && activeEdge.source !== tblName && activeEdge.target !== tblName)
                        }
                        showAllColumns={showAllColumns}
                        onSelect={onSelectTable}
                        onHover={setHoveredTable}
                        onLeave={() => setHoveredTable(null)}
                        onSelectEdge={setActiveEdge}
                        onInspect={onInspectTable}
                        onBrowse={onBrowseRecords}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Relational Matrix View */}
      {viewMode === 'matrix' && (
        <div className="erd-matrix-container">
          <div className="erd-matrix-header">
            <div>
              <h3>Relational Schema Matrix</h3>
              <p className="muted" style={{ margin: 0, fontSize: 12 }}>
                Directory of all {edges.length} foreign key relationships and table connection mappings.
              </p>
            </div>
          </div>
          <table className="erd-matrix-table">
            <thead>
              <tr>
                <th scope="col">Child Table (Foreign Key)</th>
                <th scope="col">Relational Connection</th>
                <th scope="col">Parent Table (Primary Key)</th>
                <th scope="col">Cardinality</th>
                <th scope="col">Domain</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {edges.map((edge) => (
                <tr key={edge.id}>
                  <td>
                    <strong>{edge.source}</strong>.<code>{edge.source_column}</code>
                  </td>
                  <td>
                    <div className="matrix-rel-flow">
                      <span className="key-badge fk"><Link2 size={10} /> FK</span>
                      <ArrowRight size={14} className="text-muted" />
                      <span className="key-badge pk"><Key size={10} /> PK</span>
                    </div>
                  </td>
                  <td>
                    <strong>{edge.target}</strong>.<code>{edge.target_column}</code>
                  </td>
                  <td>
                    <span className="erd-cardinality-badge">1-to-many (1:N)</span>
                  </td>
                  <td>
                    <span className="type-badge type-badge-other">
                      {bruvTables.has(edge.source) ? 'BRUV Pipeline' : 'Security / System'}
                    </span>
                  </td>
                  <td>
                    <div className="matrix-actions">
                      <button
                        type="button"
                        className="ghost-button compact"
                        onClick={() => {
                          onSelectTable(edge.source);
                          setActiveEdge(edge);
                          setViewMode('canvas');
                        }}
                      >
                        <Network size={12} /> Focus in Canvas
                      </button>
                      <button
                        type="button"
                        className="ghost-button compact"
                        onClick={() => onInspectTable(edge.source)}
                      >
                        Inspect
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Mermaid Code View */}
      {viewMode === 'mermaid' && (
        <div className="schema-export-container">
          <div className="export-panel">
            <div className="export-panel-header">
              <div>
                <h3>Mermaid Entity-Relationship Diagram</h3>
                <p className="muted">
                  Ready-to-use Mermaid ERD definition with connection syntax for GitHub markdown and diagrams.
                </p>
              </div>
              <button
                type="button"
                className="ghost-button compact"
                onClick={() => copyToClipboard(mermaidText, 'mermaid-tab')}
              >
                {copiedType === 'mermaid-tab' ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                {copiedType === 'mermaid-tab' ? 'Copied!' : 'Copy Mermaid ERD'}
              </button>
            </div>
            <pre className="code-block">
              <code>{mermaidText}</code>
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DatabaseSchema({
  initialTable = 'observations',
  onSelectTableInBrowser = null,
}) {
  const [schemaData, setSchemaData] = useState({ loading: true, data: null, error: '' });
  const [activeTab, setActiveTab] = useState('diagram'); // 'diagram' | 'inspector' | 'export'
  const [selectedTable, setSelectedTable] = useState(initialTable);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterDomain, setFilterDomain] = useState('all'); // 'all' | 'bruv' | 'auth'
  const [copiedType, setCopiedType] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    request('/tables/schema', controller.signal)
      .then((data) => setSchemaData({ loading: false, data, error: '' }))
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setSchemaData({ loading: false, data: null, error: err.message || 'Failed to fetch schema' });
        }
      });
    return () => controller.abort();
  }, []);

  const { loading, data, error } = schemaData;
  const tables = useMemo(() => data?.tables || [], [data]);
  const edges = useMemo(() => data?.edges || [], [data]);
  const summary = useMemo(
    () => data?.summary || { total_tables: 0, total_columns: 0, total_relationships: 0, total_records: 0 },
    [data]
  );

  const currentTableSchema = useMemo(() => {
    return tables.find((t) => t.name === selectedTable) || tables[0] || null;
  }, [tables, selectedTable]);

  // BRUV domain vs Auth domain grouping
  const bruvTables = useMemo(
    () => new Set(['projects', 'fieldtrips', 'deployments', 'observations', 'measurements', 'calibrations', 'day_sheets', 'analysis_periods']),
    []
  );

  const filteredTables = useMemo(() => {
    return tables
      .filter((t) => {
        const matchesSearch =
          `${t.name} ${t.label}`.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.columns.some((c) => c.name.toLowerCase().includes(searchQuery.toLowerCase()));
        if (!matchesSearch) return false;
        if (filterDomain === 'bruv') return bruvTables.has(t.name);
        if (filterDomain === 'auth') return !bruvTables.has(t.name);
        return true;
      })
      .sort((a, b) => {
        const idxA = SURVEY_TABLES_ORDER.indexOf(a.name);
        const idxB = SURVEY_TABLES_ORDER.indexOf(b.name);
        if (idxA !== -1 && idxB !== -1) return idxA - idxB;
        if (idxA !== -1) return -1;
        if (idxB !== -1) return 1;
        return a.label.localeCompare(b.label);
      });
  }, [tables, searchQuery, filterDomain, bruvTables]);

  const mermaidErd = useMemo(() => (tables.length ? generateMermaidErd(tables, edges) : ''), [tables, edges]);
  const sqlDdl = useMemo(() => (tables.length ? generateSqlDdl(tables) : ''), [tables]);

  function copyToClipboard(text, type) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedType(type);
      setTimeout(() => setCopiedType(''), 2500);
    });
  }

  if (loading) {
    return (
      <div className="schema-view-wrapper">
        <div className="empty-state" role="status">
          <RefreshCw size={28} className="spin" />
          <h3>Loading PostgreSQL database schema…</h3>
          <p className="muted">Inspecting tables, columns, constraints, and relationships.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="schema-view-wrapper">
        <div className="error-banner" role="alert">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="schema-view-wrapper">
      <div className="schema-top-header">
        <div className="schema-top-left">
          <p className="eyebrow">POSTGRESQL ARCHITECTURE</p>
          <h1>Database Schema & ER Relationships</h1>
          <p className="muted">
            Explore table structures, data types, primary & foreign keys, and relational cardinality in the marine data warehouse.
          </p>
        </div>
        <div className="schema-summary-strip">
          <div className="summary-chip">
            <Database size={15} />
            <div>
              <strong>{summary.total_tables}</strong>
              <span>Tables</span>
            </div>
          </div>
          <div className="summary-chip">
            <Layers size={15} />
            <div>
              <strong>{summary.total_columns}</strong>
              <span>Columns</span>
            </div>
          </div>
          <div className="summary-chip">
            <Network size={15} />
            <div>
              <strong>{summary.total_relationships}</strong>
              <span>FK Links</span>
            </div>
          </div>
          <div className="summary-chip">
            <Table2 size={15} />
            <div>
              <strong>{summary.total_records.toLocaleString()}</strong>
              <span>Total rows</span>
            </div>
          </div>
        </div>
      </div>

      <div className="schema-toolbar">
        <div className="schema-nav-tabs" role="tablist" aria-label="Schema views">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'diagram'}
            className={activeTab === 'diagram' ? 'active' : ''}
            onClick={() => setActiveTab('diagram')}
          >
            <Network size={16} /> ER Diagram & Visual Map
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'inspector'}
            className={activeTab === 'inspector' ? 'active' : ''}
            onClick={() => setActiveTab('inspector')}
          >
            <Table2 size={16} /> Table Schema Inspector ({tables.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'export'}
            className={activeTab === 'export' ? 'active' : ''}
            onClick={() => setActiveTab('export')}
          >
            <FileCode size={16} /> SQL DDL & Mermaid Export
          </button>
        </div>

        <div className="schema-filter-bar">
          <label className="schema-search-box">
            <Search size={15} />
            <input
              type="text"
              placeholder="Search table or column name…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </label>
          <div className="domain-filter-group">
            <button
              type="button"
              className={filterDomain === 'all' ? 'active' : ''}
              onClick={() => setFilterDomain('all')}
            >
              All Tables ({tables.length})
            </button>
            <button
              type="button"
              className={filterDomain === 'bruv' ? 'active' : ''}
              onClick={() => setFilterDomain('bruv')}
            >
              Survey Data
            </button>
            <button
              type="button"
              className={filterDomain === 'auth' ? 'active' : ''}
              onClick={() => setFilterDomain('auth')}
            >
              Users & System
            </button>
          </div>
        </div>
      </div>

      {activeTab === 'diagram' && (
        <ErdDiagramCanvas
          tables={tables}
          edges={edges}
          selectedTable={selectedTable}
          onSelectTable={(tblName) => setSelectedTable(tblName)}
          onInspectTable={(tblName) => {
            setSelectedTable(tblName);
            setActiveTab('inspector');
          }}
          onBrowseRecords={onSelectTableInBrowser}
          filterDomain={filterDomain}
          copyToClipboard={copyToClipboard}
          copiedType={copiedType}
        />
      )}

      {activeTab === 'inspector' && (
        <div className="schema-inspector-layout">
          <div className="inspector-sidebar">
            <div className="inspector-sidebar-header">
              <span>TABLES</span>
              <span className="count">{filteredTables.length}</span>
            </div>
            <nav className="inspector-table-list">
              {filteredTables.map((t) => {
                const isSelected = t.name === (currentTableSchema?.name || selectedTable);
                return (
                  <button
                    key={t.name}
                    type="button"
                    className={`inspector-table-item ${isSelected ? 'active' : ''}`}
                    onClick={() => setSelectedTable(t.name)}
                  >
                    <Table2 size={15} />
                    <div className="inspector-table-names">
                      <strong>{t.label}</strong>
                      <code>{t.name}</code>
                    </div>
                    <span className="col-count-badge" title={`${t.columns.length} columns`}>
                      {t.columns.length}
                    </span>
                  </button>
                );
              })}
              {filteredTables.length === 0 && (
                <p className="sidebar-message">No tables match your filter.</p>
              )}
            </nav>
          </div>

          <div className="inspector-content">
            {currentTableSchema ? (
              <SingleTableSchemaView
                table={currentTableSchema}
                schemaData={currentTableSchema}
                onNavigateTable={(targetName) => {
                  setSelectedTable(targetName);
                }}
                onOpenFullDiagram={() => setActiveTab('diagram')}
                onNavigateToRecords={onSelectTableInBrowser}
              />
            ) : (
              <div className="empty-state">
                <p>Select a table to inspect its schema.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'export' && (
        <div className="schema-export-container">
          <div className="export-panel">
            <div className="export-panel-header">
              <div>
                <h3>Mermaid Entity-Relationship Diagram</h3>
                <p className="muted">
                  Use in Markdown documents, GitHub documentation, or Mermaid Live Editor.
                </p>
              </div>
              <button
                type="button"
                className="ghost-button compact"
                onClick={() => copyToClipboard(mermaidErd, 'mermaid')}
              >
                {copiedType === 'mermaid' ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                {copiedType === 'mermaid' ? 'Copied!' : 'Copy Mermaid ERD'}
              </button>
            </div>
            <pre className="code-block">
              <code>{mermaidErd}</code>
            </pre>
          </div>

          <div className="export-panel">
            <div className="export-panel-header">
              <div>
                <h3>PostgreSQL SQL DDL (Table Definitions)</h3>
                <p className="muted">
                  Synthesized SQL CREATE TABLE statements for backup, database reproduction, and Specify 7 integration.
                </p>
              </div>
              <button
                type="button"
                className="ghost-button compact"
                onClick={() => copyToClipboard(sqlDdl, 'sql')}
              >
                {copiedType === 'sql' ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                {copiedType === 'sql' ? 'Copied!' : 'Copy SQL DDL'}
              </button>
            </div>
            <pre className="code-block">
              <code>{sqlDdl}</code>
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
