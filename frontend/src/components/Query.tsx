import React, {
  useState,
  useEffect,
  useMemo,
  useRef,
  useCallback,
} from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  IconButton,
  InputLabel,
  List,
  ListItemButton,
  ListItemText,
  ListSubheader,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
  Typography,
  LinearProgress,
} from "@mui/material";
import {
  PlayArrow as ExecuteIcon,
  Clear as ClearIcon,
  History as HistoryIcon,
  Refresh as RefreshIcon,
  TableRows as TableRowsIcon,
  AutoAwesome as AutoAwesomeIcon,
  ContentCopy as ContentCopyIcon,
} from "@mui/icons-material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import Editor from "@monaco-editor/react";
import type * as Monaco from "monaco-editor";
import {
  Connection,
  QueryRequest,
  Table,
  connectionApi,
  automationApi,
} from "../services/api";

interface QueryResult {
  columns?: string[];
  rows?: any[][];
  error?: string;
  execution_time?: number;
}

interface QueryHistoryEntry {
  id: string;
  query: string;
  status: "success" | "error";
  timestamp: string;
  executionTime?: number;
  rowsReturned?: number;
}

const SQL_KEYWORDS = [
  "SELECT",
  "INSERT",
  "UPDATE",
  "DELETE",
  "CREATE",
  "ALTER",
  "DROP",
  "FROM",
  "WHERE",
  "GROUP BY",
  "ORDER BY",
  "LIMIT",
  "JOIN",
  "LEFT JOIN",
  "RIGHT JOIN",
  "INNER JOIN",
  "OUTER JOIN",
  "ON",
  "AS",
  "AND",
  "OR",
];

const SAMPLE_QUERIES = [
  {
    label: "List schemas",
    query: "SELECT schema_name FROM information_schema.schemata;",
  },
  {
    label: "Inspect tables",
    query:
      "SELECT table_schema, table_name FROM information_schema.tables LIMIT 50;",
  },
  {
    label: "Count rows template",
    query: "SELECT COUNT(*) AS total_rows FROM <schema>.<table>;",
  },
  {
    label: "Show recent rows",
    query: "SELECT * FROM <schema>.<table> ORDER BY 1 DESC LIMIT 100;",
  },
];

const Query: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [schemas, setSchemas] = useState<string[]>([]);
  const [tables, setTables] = useState<Table[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | "">("");
  const [selectedSchema, setSelectedSchema] = useState<string>("");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [schemasLoading, setSchemasLoading] = useState(false);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({
    open: false,
    message: "",
    severity: "success",
  });
  const [tableFilter, setTableFilter] = useState("");
  const [history, setHistory] = useState<QueryHistoryEntry[]>([]);

  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof Monaco | null>(null);
  const completionDisposableRef = useRef<Monaco.IDisposable | null>(null);
  const executeCommandRef = useRef<() => void>(() => undefined);

  const filteredTables = useMemo(() => {
    if (!tableFilter.trim()) {
      return tables;
    }
    const filter = tableFilter.toLowerCase();
    return tables.filter(
      (table) =>
        table.name.toLowerCase().includes(filter) ||
        (table.schema && table.schema.toLowerCase().includes(filter))
    );
  }, [tables, tableFilter]);

  const gridColumns: GridColDef[] = useMemo(() => {
    if (!result?.columns) {
      return [];
    }
    return result.columns.map((column) => ({
      field: column,
      headerName: column,
      flex: 1,
      minWidth: 140,
    }));
  }, [result?.columns]);

  const gridRows = useMemo(() => {
    if (!result?.rows || !result.columns) {
      return [];
    }
    return result.rows.map((row, idx) => {
      const rowObj: Record<string, any> = { id: idx };
      result.columns!.forEach((col, colIdx) => {
        rowObj[col] = row[colIdx];
      });
      return rowObj;
    });
  }, [result?.rows, result?.columns]);

  const showSnackbar = useCallback(
    (message: string, severity: "success" | "error") => {
      setSnackbar({ open: true, message, severity });
    },
    []
  );

  const handleCloseSnackbar = () => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  };

  const loadConnections = useCallback(async () => {
    try {
      const data = await connectionApi.list();
      setConnections(data);
      if (data.length > 0) {
        setSelectedConnection((prev) => prev || data[0].id || "");
      }
    } catch (error) {
      showSnackbar("Failed to load connections", "error");
    }
  }, [showSnackbar]);

  const loadSchemas = useCallback(
    async (connectionId: number) => {
      setSchemasLoading(true);
      try {
        const data = await connectionApi.getSchemas(connectionId);
        setSchemas(data);
        if (data.length > 0) {
          setSelectedSchema((prev) => prev || data[0]);
        } else {
          setSelectedSchema("");
        }
      } catch (error) {
        showSnackbar("Unable to load schemas for this connection", "error");
        setSchemas([]);
        setSelectedSchema("");
      } finally {
        setSchemasLoading(false);
      }
    },
    [showSnackbar]
  );

  const loadTables = useCallback(
    async (connectionId: number, schema?: string) => {
      if (!schema) {
        setTables([]);
        return;
      }
      setTablesLoading(true);
      try {
        const data = await connectionApi.getTables(connectionId, schema);
        setTables(data);
      } catch (error) {
        showSnackbar("Unable to load tables for the selected schema", "error");
        setTables([]);
      } finally {
        setTablesLoading(false);
      }
    },
    [showSnackbar]
  );

  const registerCompletionProvider = useCallback(() => {
    if (!monacoRef.current) return;
    completionDisposableRef.current?.dispose();

    const monaco = monacoRef.current;
    const keywordSuggestions = SQL_KEYWORDS.map((keyword) => ({
      label: keyword,
      kind: monaco.languages.CompletionItemKind.Keyword,
      insertText: keyword,
    }));

    const tableSuggestions = tables.map((table) => {
      const qualifiedName = table.schema
        ? `${table.schema}.${table.name}`
        : table.name;
      return {
        label: qualifiedName,
        kind: monaco.languages.CompletionItemKind.Field,
        detail: "Table",
        insertText: qualifiedName,
      };
    });

    completionDisposableRef.current =
      monaco.languages.registerCompletionItemProvider("sql", {
        provideCompletionItems: () => ({
          suggestions: [...keywordSuggestions, ...tableSuggestions],
        }),
      });
  }, [tables]);

  const handleExecuteQuery = useCallback(async () => {
    if (!selectedConnection || !query.trim()) {
      showSnackbar("Select a connection and write a query first", "error");
      return;
    }

    setLoading(true);
    const startTime = Date.now();

    try {
      const request: QueryRequest = {
        connection_id: Number(selectedConnection),
        query: query.trim(),
      };
      const response = await automationApi.executeQuery(request);
      const executionTime = Date.now() - startTime;

      const transformedResult: QueryResult = {
        execution_time: executionTime,
      };

      if (response.success) {
        const rows: any[][] = [];
        if (response.results && response.column_names) {
          for (const rowDict of response.results) {
            rows.push(
              response.column_names.map(
                (columnName: string) => rowDict[columnName]
              )
            );
          }
        }
        transformedResult.columns = response.column_names || [];
        transformedResult.rows = rows;
      } else {
        transformedResult.error = response.message;
      }

      setResult(transformedResult);
      const historyEntry: QueryHistoryEntry = {
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`,
        query: query.trim(),
        status: response.success ? "success" : "error",
        timestamp: new Date().toISOString(),
        executionTime: transformedResult.execution_time,
        rowsReturned: transformedResult.rows?.length,
      };
      setHistory((prev) => [historyEntry, ...prev].slice(0, 25));

      showSnackbar(
        response.success ? "Query executed successfully" : "Query failed",
        response.success ? "success" : "error"
      );
    } catch (error: any) {
      const executionTime = Date.now() - startTime;
      const message =
        error.response?.data?.detail ||
        error.message ||
        "Query execution failed";
      setResult({
        error: message,
        execution_time: executionTime,
      });
      const historyEntry: QueryHistoryEntry = {
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`,
        query: query.trim(),
        status: "error",
        timestamp: new Date().toISOString(),
        executionTime,
      };
      setHistory((prev) => [historyEntry, ...prev].slice(0, 25));
      showSnackbar(message, "error");
    } finally {
      setLoading(false);
    }
  }, [query, selectedConnection, showSnackbar]);

  const handleClear = () => {
    setQuery("");
    setResult(null);
  };

  const handleSampleQuery = (sampleQuery: string) => {
    setQuery(sampleQuery);
  };

  const handleTableSnippet = (table: Table) => {
    const qualifiedName = table.schema
      ? `${table.schema}.${table.name}`
      : table.name;
    const snippet = `SELECT *\nFROM ${qualifiedName}\nLIMIT 100;`;
    setQuery((prev) => (prev ? `${prev.trim()}\n\n${snippet}` : snippet));
  };

  const handleHistorySelect = (entry: QueryHistoryEntry) => {
    setQuery(entry.query);
  };

  const handleEditorMount = useCallback(
    (editor: Monaco.editor.IStandaloneCodeEditor, monaco: typeof Monaco) => {
      editorRef.current = editor;
      monacoRef.current = monaco;
      registerCompletionProvider();

      const runShortcut = monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter;
      editor.addCommand(runShortcut, () => executeCommandRef.current());
    },
    [registerCompletionProvider]
  );

  useEffect(() => {
    executeCommandRef.current = () => {
      void handleExecuteQuery();
    };
  }, [handleExecuteQuery]);

  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  useEffect(() => {
    if (selectedConnection) {
      loadSchemas(Number(selectedConnection));
    } else {
      setSchemas([]);
      setSelectedSchema("");
    }
  }, [selectedConnection, loadSchemas]);

  useEffect(() => {
    if (selectedConnection && selectedSchema) {
      loadTables(Number(selectedConnection), selectedSchema);
    } else {
      setTables([]);
    }
  }, [selectedConnection, selectedSchema, loadTables]);

  useEffect(() => {
    registerCompletionProvider();
  }, [registerCompletionProvider]);

  useEffect(
    () => () => {
      completionDisposableRef.current?.dispose();
    },
    []
  );

  const selectedConnectionMeta = useMemo(
    () => connections.find((conn) => conn.id === Number(selectedConnection)),
    [connections, selectedConnection]
  );

  const renderMetadataPanel = () => (
    <Stack spacing={2} sx={{ height: "100%", overflow: "auto", pr: 1 }}>
      <Paper variant="outlined">
        <Stack spacing={2} p={2}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Connection
            </Typography>
            <FormControl fullWidth size="small" sx={{ mt: 1 }}>
              <InputLabel>Database Connection</InputLabel>
              <Select
                label="Database Connection"
                value={selectedConnection}
                onChange={(e) => {
                  setSelectedConnection(e.target.value as number | "");
                  setSelectedSchema("");
                  setTables([]);
                }}
              >
                {connections.map((connection) => (
                  <MenuItem key={connection.id} value={connection.id}>
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        width: "100%",
                        gap: 2,
                      }}
                    >
                      <span>{connection.name}</span>
                      <Typography variant="caption" color="text.secondary">
                        {connection.db_type?.toUpperCase()}
                      </Typography>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            justifyContent="space-between"
          >
            <Typography variant="subtitle2" color="text.secondary">
              Schema
            </Typography>
            <Tooltip title="Reload schemas">
              <span>
                <IconButton
                  size="small"
                  onClick={() =>
                    selectedConnection &&
                    loadSchemas(Number(selectedConnection))
                  }
                  disabled={!selectedConnection || schemasLoading}
                >
                  <RefreshIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
          <FormControl fullWidth size="small">
            <InputLabel>Schema</InputLabel>
            <Select
              label="Schema"
              value={selectedSchema}
              onChange={(e) => setSelectedSchema(e.target.value)}
              disabled={!selectedConnection || schemas.length === 0}
            >
              {schemas.map((schema) => (
                <MenuItem key={schema} value={schema}>
                  {schema}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {schemasLoading && <LinearProgress />}
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ flex: 1, minHeight: 260 }}>
        <Stack spacing={1.5} p={2} sx={{ height: "100%" }}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
          >
            <Stack direction="row" spacing={1} alignItems="center">
              <TableRowsIcon fontSize="small" color="action" />
              <Typography variant="subtitle2">Tables</Typography>
            </Stack>
            <Tooltip title="Reload tables for schema">
              <span>
                <IconButton
                  size="small"
                  onClick={() =>
                    selectedConnection &&
                    selectedSchema &&
                    loadTables(Number(selectedConnection), selectedSchema)
                  }
                  disabled={
                    !selectedConnection || !selectedSchema || tablesLoading
                  }
                >
                  <RefreshIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
          <TextField
            size="small"
            placeholder="Filter tables"
            value={tableFilter}
            onChange={(e) => setTableFilter(e.target.value)}
          />
          <Divider />
          <Box sx={{ flex: 1, overflow: "auto" }}>
            {tablesLoading ? (
              <Stack
                spacing={2}
                alignItems="center"
                justifyContent="center"
                sx={{ height: "100%" }}
              >
                <CircularProgress size={24} />
                <Typography variant="caption" color="text.secondary">
                  Loading tables...
                </Typography>
              </Stack>
            ) : filteredTables.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                {selectedSchema
                  ? "No tables match this filter"
                  : "Select a schema to browse tables"}
              </Typography>
            ) : (
              <List dense>
                {filteredTables.map((table) => (
                  <ListItemButton
                    key={`${table.schema}-${table.name}`}
                    onClick={() => handleTableSnippet(table)}
                  >
                    <ListItemText
                      primary={table.name}
                      secondary={table.schema || selectedSchema}
                      primaryTypographyProps={{
                        fontSize: "0.9rem",
                        fontWeight: 500,
                      }}
                      secondaryTypographyProps={{ fontSize: "0.75rem" }}
                    />
                    <Tooltip title="Insert SELECT * snippet">
                      <IconButton
                        size="small"
                        edge="end"
                        onClick={(event) => {
                          event.stopPropagation();
                          handleTableSnippet(table);
                        }}
                      >
                        <ContentCopyIcon fontSize="inherit" />
                      </IconButton>
                    </Tooltip>
                  </ListItemButton>
                ))}
              </List>
            )}
          </Box>
        </Stack>
      </Paper>

      <Paper variant="outlined">
        <Stack spacing={1.5} p={2}>
          <Stack direction="row" spacing={1} alignItems="center">
            <AutoAwesomeIcon fontSize="small" color="action" />
            <Typography variant="subtitle2">Sample Queries</Typography>
          </Stack>
          <Stack spacing={1}>
            {SAMPLE_QUERIES.map((sample) => (
              <Button
                key={sample.label}
                size="small"
                variant="outlined"
                onClick={() => handleSampleQuery(sample.query)}
              >
                {sample.label}
              </Button>
            ))}
          </Stack>
        </Stack>
      </Paper>

      <Paper variant="outlined">
        <Stack spacing={1} p={2}>
          <Stack direction="row" spacing={1} alignItems="center">
            <HistoryIcon fontSize="small" color="action" />
            <Typography variant="subtitle2">Recent Runs</Typography>
          </Stack>
          {history.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Execute a query to start tracking history.
            </Typography>
          ) : (
            <List
              dense
              subheader={
                <ListSubheader disableSticky disableGutters>
                  Latest 25 statements
                </ListSubheader>
              }
              sx={{ maxHeight: 180, overflow: "auto" }}
            >
              {history.map((entry) => (
                <ListItemButton
                  key={entry.id}
                  onClick={() => handleHistorySelect(entry)}
                >
                  <Stack
                    direction="row"
                    spacing={1}
                    alignItems="center"
                    sx={{ width: "100%" }}
                  >
                    <Chip
                      size="small"
                      label={entry.status === "success" ? "OK" : "ERR"}
                      color={entry.status === "success" ? "success" : "error"}
                      sx={{ minWidth: 56 }}
                    />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="body2"
                        noWrap
                        sx={{ fontWeight: 500 }}
                      >
                        {entry.query.replace(/\s+/g, " ").slice(0, 80)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(entry.timestamp).toLocaleTimeString()} ·{" "}
                        {entry.executionTime
                          ? `${entry.executionTime} ms`
                          : "—"}
                      </Typography>
                    </Box>
                  </Stack>
                </ListItemButton>
              ))}
            </List>
          )}
        </Stack>
      </Paper>
    </Stack>
  );

  return (
    <Box
      sx={{
        height: "calc(100vh - 120px)",
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", sm: "center" }}
        spacing={1}
      >
        <Box>
          <Typography variant="h4">Query Browser</Typography>
          <Typography variant="body2" color="text.secondary">
            DataGrip-inspired workspace with full-page editor, autocomplete, and
            result grids.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          {selectedConnectionMeta && (
            <Chip
              label={`${
                selectedConnectionMeta.name
              } · ${selectedConnectionMeta.db_type?.toUpperCase()}`}
              color="primary"
              variant="outlined"
            />
          )}
          <Chip label="⌘ / Ctrl + Enter to run" variant="outlined" />
        </Stack>
      </Stack>

      <Box
        sx={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: { xs: "1fr", lg: "320px 1fr" },
          gap: 2,
          minHeight: 0,
        }}
      >
        {renderMetadataPanel()}

        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: 2,
            minHeight: 0,
          }}
        >
          <Paper
            variant="outlined"
            sx={{
              flex: 1,
              minHeight: 280,
              display: "flex",
              flexDirection: "column",
            }}
          >
            <Stack direction="row" alignItems="center" spacing={1} p={2}>
              <Tooltip title="Run (⌘ / Ctrl + Enter)">
                <span>
                  <Button
                    variant="contained"
                    startIcon={
                      loading ? (
                        <CircularProgress size={18} color="inherit" />
                      ) : (
                        <ExecuteIcon />
                      )
                    }
                    onClick={handleExecuteQuery}
                    disabled={loading || !selectedConnection || !query.trim()}
                  >
                    {loading ? "Executing" : "Run"}
                  </Button>
                </span>
              </Tooltip>
              <Button
                variant="outlined"
                startIcon={<ClearIcon />}
                onClick={handleClear}
              >
                Clear
              </Button>
              <Box sx={{ flex: 1 }} />
              {result?.execution_time && (
                <Chip
                  size="small"
                  label={`Execution: ${result.execution_time} ms`}
                />
              )}
              {result?.rows && (
                <Chip
                  size="small"
                  label={`${result.rows.length} rows`}
                  variant="outlined"
                />
              )}
            </Stack>
            <Divider />
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <Editor
                height="100%"
                defaultLanguage="sql"
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontFamily: '"JetBrains Mono", Menlo, monospace',
                  fontSize: 14,
                  automaticLayout: true,
                  scrollBeyondLastLine: false,
                  wordWrap: "on",
                  renderLineHighlight: "all",
                  suggestOnTriggerCharacters: true,
                }}
                value={query}
                onChange={(value) => setQuery(value ?? "")}
                onMount={handleEditorMount}
              />
            </Box>
          </Paper>

          <Paper
            variant="outlined"
            sx={{
              flex: 1,
              minHeight: 260,
              display: "flex",
              flexDirection: "column",
            }}
          >
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              p={2}
            >
              <Typography variant="subtitle1">Result Grid</Typography>
              {loading && (
                <Stack direction="row" spacing={1} alignItems="center">
                  <CircularProgress size={16} />
                  <Typography variant="body2" color="text.secondary">
                    Running query...
                  </Typography>
                </Stack>
              )}
            </Stack>
            <Divider />
            <Box sx={{ flex: 1, minHeight: 0 }}>
              {loading ? (
                <LinearProgress />
              ) : result?.error ? (
                <Alert severity="error" sx={{ m: 2 }}>
                  {result.error}
                </Alert>
              ) : gridRows.length > 0 ? (
                <DataGrid
                  rows={gridRows}
                  columns={gridColumns}
                  density="compact"
                  disableRowSelectionOnClick
                  sx={{ border: "none" }}
                />
              ) : result ? (
                <Alert severity="info" sx={{ m: 2 }}>
                  Query executed successfully. No rows returned.
                </Alert>
              ) : (
                <Stack
                  spacing={1}
                  alignItems="center"
                  justifyContent="center"
                  sx={{ height: "100%" }}
                >
                  <Typography variant="body2" color="text.secondary">
                    Run a query to see results here.
                  </Typography>
                </Stack>
              )}
            </Box>
          </Paper>
        </Box>
      </Box>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Query;
