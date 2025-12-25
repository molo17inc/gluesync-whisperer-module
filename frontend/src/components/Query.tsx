import React, {
  useState,
  useEffect,
  useMemo,
  useRef,
  useCallback,
} from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  IconButton,
  InputLabel,
  LinearProgress,
  List,
  ListItemButton,
  Menu,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  PlayArrow as ExecuteIcon,
  Clear as ClearIcon,
  History as HistoryIcon,
  Refresh as RefreshIcon,
  AutoAwesome as AutoAwesomeIcon,
  ContentCopy as ContentCopyIcon,
  ExpandMore as ExpandMoreIcon,
  KeyboardArrowDown as ArrowDropDownIcon,
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
  const [history, setHistory] = useState<QueryHistoryEntry[]>([]);
  const [tablePickerSelection, setTablePickerSelection] =
    useState<Table | null>(null);
  const [sampleMenuAnchor, setSampleMenuAnchor] = useState<null | HTMLElement>(
    null
  );
  const [historyExpanded, setHistoryExpanded] = useState(false);

  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof Monaco | null>(null);
  const completionDisposableRef = useRef<Monaco.IDisposable | null>(null);
  const executeCommandRef = useRef<() => void>(() => undefined);

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

  const handleTablePickerChange = (_: any, value: Table | null) => {
    setTablePickerSelection(value);
    if (value) {
      handleTableSnippet(value);
    }
  };

  const handleSampleMenuToggle = (event: React.MouseEvent<HTMLElement>) => {
    setSampleMenuAnchor(event.currentTarget);
  };

  const handleSampleMenuClose = () => {
    setSampleMenuAnchor(null);
  };

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

    completionDisposableRef.current =
      monaco.languages.registerCompletionItemProvider("sql", {
        provideCompletionItems: (model, position) => {
          const word = model.getWordUntilPosition(position);
          const range = {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: word.startColumn,
            endColumn: word.endColumn,
          };

          const keywordSuggestions: Monaco.languages.CompletionItem[] =
            SQL_KEYWORDS.map((keyword) => ({
              label: keyword,
              kind: monaco.languages.CompletionItemKind.Keyword,
              insertText: keyword,
              range,
            }));

          const tableSuggestions: Monaco.languages.CompletionItem[] =
            tables.map((table) => {
              const qualifiedName = table.schema
                ? `${table.schema}.${table.name}`
                : table.name;
              return {
                label: qualifiedName,
                kind: monaco.languages.CompletionItemKind.Field,
                detail: "Table",
                insertText: qualifiedName,
                range,
              };
            });

          return {
            suggestions: [...keywordSuggestions, ...tableSuggestions],
          };
        },
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
    setTablePickerSelection(null);
  }, [selectedConnection, selectedSchema]);

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
          <Typography variant="h4">Query browser</Typography>
          <Typography variant="body2" color="text.secondary">
            Query editor workspace with full-page editor, autocomplete, and
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

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack
          direction={{ xs: "column", lg: "row" }}
          spacing={2}
          alignItems={{ lg: "center" }}
          flexWrap="wrap"
        >
          <FormControl size="small" sx={{ minWidth: 220 }}>
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
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            sx={{ flex: 1 }}
          >
            <Autocomplete
              size="small"
              sx={{ minWidth: 200, flex: 1 }}
              options={schemas}
              value={selectedSchema}
              onChange={(_, value) => setSelectedSchema(value ?? "")}
              loading={schemasLoading}
              disabled={!selectedConnection || schemas.length === 0}
              getOptionLabel={(option) => option}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Schema"
                  placeholder={
                    !selectedConnection
                      ? "Select a connection first"
                      : schemas.length === 0
                      ? "No schemas found"
                      : "Search schemas"
                  }
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {schemasLoading ? (
                          <CircularProgress color="inherit" size={16} />
                        ) : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
            />
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
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            sx={{ flex: 1, minWidth: 240 }}
          >
            <Autocomplete
              size="small"
              sx={{ flex: 1 }}
              options={tables}
              value={tablePickerSelection}
              onChange={handleTablePickerChange}
              getOptionLabel={(option) =>
                option.schema
                  ? `${option.schema}.${option.name}`
                  : option.name ?? ""
              }
              isOptionEqualToValue={(option, value) =>
                option.schema === value?.schema && option.name === value?.name
              }
              loading={tablesLoading}
              disabled={
                !selectedConnection || !selectedSchema || tables.length === 0
              }
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Table"
                  placeholder={
                    !selectedSchema ? "Select a schema first" : "Search tables"
                  }
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {tablesLoading ? (
                          <CircularProgress color="inherit" size={16} />
                        ) : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
            />
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
            <Tooltip title="Insert SELECT * for highlighted table">
              <span>
                <IconButton
                  size="small"
                  onClick={() => {
                    if (tablePickerSelection) {
                      handleTableSnippet(tablePickerSelection);
                    }
                  }}
                  disabled={!tablePickerSelection}
                >
                  <ContentCopyIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
        </Stack>
        {(schemasLoading || tablesLoading) && <LinearProgress sx={{ mt: 2 }} />}
      </Paper>

      <Box
        sx={{
          flex: 1,
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
            <Button
              variant="text"
              startIcon={<AutoAwesomeIcon />}
              endIcon={<ArrowDropDownIcon />}
              onClick={handleSampleMenuToggle}
            >
              Sample queries
            </Button>
            <Menu
              anchorEl={sampleMenuAnchor}
              open={Boolean(sampleMenuAnchor)}
              onClose={handleSampleMenuClose}
            >
              {SAMPLE_QUERIES.map((sample) => (
                <MenuItem
                  key={sample.label}
                  onClick={() => {
                    handleSampleQuery(sample.query);
                    handleSampleMenuClose();
                  }}
                >
                  {sample.label}
                </MenuItem>
              ))}
            </Menu>
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

      <Accordion
        expanded={historyExpanded}
        onChange={(_, expanded) => setHistoryExpanded(expanded)}
        disableGutters
        sx={{ borderRadius: 1, border: "1px solid", borderColor: "divider" }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Stack direction="row" spacing={1} alignItems="center">
            <HistoryIcon fontSize="small" color="action" />
            <Typography variant="subtitle2">
              Recent Runs ({history.length})
            </Typography>
          </Stack>
        </AccordionSummary>
        <AccordionDetails>
          {history.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Execute a query to start tracking history.
            </Typography>
          ) : (
            <List dense sx={{ maxHeight: 240, overflow: "auto" }}>
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
        </AccordionDetails>
      </Accordion>

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
