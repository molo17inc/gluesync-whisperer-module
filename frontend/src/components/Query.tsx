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
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
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
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import { TreeView } from "@mui/x-tree-view/TreeView";
import {
  PlayArrow as ExecuteIcon,
  Clear as ClearIcon,
  History as HistoryIcon,
  AutoAwesome as AutoAwesomeIcon,
  ExpandMore as ExpandMoreIcon,
  KeyboardArrowDown as ArrowDropDownIcon,
} from "@mui/icons-material";
import { DataGrid } from "@mui/x-data-grid";
import Editor from "@monaco-editor/react";
import type * as Monaco from "monaco-editor";
import {
  Connection,
  QueryRequest,
  Table,
  connectionApi,
  automationApi,
  metadataApi,
  MetadataObject,
  TableMetadata,
} from "../services/api";

interface QueryResult {
  columns?: string[];
  rows?: any[][];
  error?: string;
  execution_time?: number;
}

interface QueryTab {
  id: string;
  title: string;
  query: string;
  result: QueryResult | null;
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
  const [tables] = useState<Table[]>([]);
  const [allSchemas, setAllSchemas] = useState<string[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | "">("");

  const handleConnectionChange = (value: number | "") => {
    setSelectedConnection(value);
    localStorage.setItem("selectedConnection", value.toString());
  };

  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "warning";
  }>({
    open: false,
    message: "",
    severity: "success",
  });
  const [history, setHistory] = useState<QueryHistoryEntry[]>([]);
  const [sampleMenuAnchor, setSampleMenuAnchor] = useState<null | HTMLElement>(
    null
  );
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [metadataBySchema, setMetadataBySchema] = useState<
    Record<string, MetadataObject[]>
  >({});
  const [metadataLoadingSchema, setMetadataLoadingSchema] = useState<
    string | null
  >(null);
  const [expandedItems, setExpandedItems] = useState<string[]>([]);
  const [tableDetailsBySchemaAndTable, setTableDetailsBySchemaAndTable] =
    useState<Record<string, Record<string, TableMetadata>>>({});
  const [tableDetailsLoading, setTableDetailsLoading] = useState<string | null>(
    null
  );
  const [metadataFilter, setMetadataFilter] = useState("");
  const [tableMetadata, setTableMetadata] = useState<TableMetadata | null>(
    null
  );
  const [tableMetadataLoading, setTableMetadataLoading] = useState(false);
  const [selectedMetadataObject, setSelectedMetadataObject] =
    useState<MetadataObject | null>(null);
  const [metadataMenuAnchor, setMetadataMenuAnchor] =
    useState<null | HTMLElement>(null);

  const [activeTab, setActiveTab] = useState(0);
  const [queryTabs, setQueryTabs] = useState<QueryTab[]>([
    {
      id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`,
      title: "Query 1",
      query: "",
      result: null,
    },
  ]);

  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof Monaco | null>(null);
  const completionDisposableRef = useRef<Monaco.IDisposable | null>(null);
  const executeCommandRef = useRef<() => void>(() => undefined);
  const tabCounterRef = useRef(1);

  const showSnackbar = useCallback(
    (message: string, severity: "success" | "error" | "warning") => {
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

      if (data.length === 0) {
        setSelectedConnection("");
        localStorage.removeItem("selectedConnection");
        showSnackbar("No database connections configured.", "warning");
        return;
      }

      const saved = localStorage.getItem("selectedConnection");
      const savedId =
        saved && saved !== "" ? Number(saved) : (null as number | null);

      const nextId: number | "" =
        savedId && data.some((conn) => conn.id === savedId)
          ? savedId
          : data[0]?.id ?? "";

      setSelectedConnection(nextId);
      if (nextId === "") {
        localStorage.removeItem("selectedConnection");
      } else {
        localStorage.setItem("selectedConnection", String(nextId));
      }
    } catch (error) {
      showSnackbar("Failed to load connections", "error");
    }
  }, [showSnackbar]);

  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  const loadSchemas = useCallback(
    async (connectionId: number) => {
      try {
        const data = await connectionApi.getSchemas(connectionId);
        setAllSchemas(data);
      } catch (error) {
        showSnackbar("Unable to load schemas for this connection", "error");
        setAllSchemas([]);
      }
    },
    [showSnackbar]
  );

  const loadMetadataForSchema = useCallback(
    async (connectionId: number, schema?: string) => {
      if (!schema) return;
      if (metadataBySchema[schema]) return;
      setMetadataLoadingSchema(schema);
      try {
        const data = await metadataApi.listObjects(connectionId, schema);
        setMetadataBySchema((prev) => ({ ...prev, [schema]: data }));
      } catch (error) {
        showSnackbar("Unable to load metadata objects", "error");
      } finally {
        setMetadataLoadingSchema(null);
      }
    },
    [metadataBySchema, showSnackbar]
  );

  const loadTableMetadata = useCallback(
    async (connectionId: number, tableName: string, schema?: string) => {
      setTableMetadataLoading(true);
      try {
        const data = await metadataApi.getTableMetadata(
          connectionId,
          tableName,
          schema
        );
        setTableMetadata(data);
      } catch (error) {
        showSnackbar("Unable to load table metadata", "error");
        setTableMetadata(null);
      } finally {
        setTableMetadataLoading(false);
      }
    },
    [showSnackbar]
  );

  const loadTableDetails = useCallback(
    async (schema: string, table: string) => {
      const key = `${schema}.${table}`;
      if (tableDetailsBySchemaAndTable[schema]?.[table]) return;
      setTableDetailsLoading(key);
      try {
        const data = await metadataApi.getTableMetadata(
          Number(selectedConnection),
          table,
          schema
        );
        setTableDetailsBySchemaAndTable((prev) => ({
          ...prev,
          [schema]: { ...prev[schema], [table]: data },
        }));
      } catch (error) {
        showSnackbar("Unable to load table details", "error");
      } finally {
        setTableDetailsLoading(null);
      }
    },
    [selectedConnection, showSnackbar, tableDetailsBySchemaAndTable]
  );

  const handleSampleMenuToggle = (event: React.MouseEvent<HTMLElement>) => {
    setSampleMenuAnchor(event.currentTarget);
  };

  const handleSampleMenuClose = () => {
    setSampleMenuAnchor(null);
  };

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
    const currentQuery = queryTabs[activeTab].query.trim();
    if (!selectedConnection || !currentQuery) {
      showSnackbar("Select a connection and write a query first", "error");
      return;
    }

    setLoading(true);
    const startTime = Date.now();

    try {
      const request: QueryRequest = {
        connection_id: Number(selectedConnection),
        query: currentQuery,
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

      setQueryTabs((prev) =>
        prev.map((tab, index) =>
          index === activeTab ? { ...tab, result: transformedResult } : tab
        )
      );

      const historyEntry: QueryHistoryEntry = {
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`,
        query: currentQuery,
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
      const historyEntry: QueryHistoryEntry = {
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`,
        query: currentQuery,
        status: "error",
        timestamp: new Date().toISOString(),
        executionTime,
      };
      setHistory((prev) => [historyEntry, ...prev].slice(0, 25));
      showSnackbar(message, "error");
    } finally {
      setLoading(false);
    }
  }, [queryTabs, activeTab, selectedConnection, showSnackbar]);

  const handleClear = () => {
    setQueryTabs((prev) =>
      prev.map((tab, index) =>
        index === activeTab ? { ...tab, query: "" } : tab
      )
    );
  };

  const handleSampleQuery = (sampleQuery: string) => {
    setQueryTabs((prev) =>
      prev.map((tab, index) =>
        index === activeTab ? { ...tab, query: sampleQuery } : tab
      )
    );
  };

  const handleTableSnippet = (table: Table) => {
    const qualifiedName = table.schema
      ? `${table.schema}.${table.name}`
      : table.name;
    const snippet = `SELECT *\nFROM ${qualifiedName}\nLIMIT 100;`;
    setQueryTabs((prev) =>
      prev.map((tab, index) =>
        index === activeTab
          ? {
              ...tab,
              query: prev[index].query
                ? `${prev[index].query.trim()}\n\n${snippet}`
                : snippet,
            }
          : tab
      )
    );
  };

  const handleNewQueryTab = () => {
    const newTab: QueryTab = {
      id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`,
      title: `Query ${tabCounterRef.current++}`,
      query: "",
      result: null,
    };
    setQueryTabs((prev) => [...prev, newTab]);
    setActiveTab(queryTabs.length);
  };

  const handleMetadataSelect = (obj: MetadataObject) => {
    if (obj.type === "table" || obj.type === "view") {
      const table: Table = { name: obj.name, schema: obj.schema };
      handleTableSnippet(table);
      loadTableMetadata(Number(selectedConnection), obj.name, obj.schema || "");
    }
  };

  const handleMetadataContextMenu = (
    event: React.MouseEvent<HTMLElement>,
    obj: MetadataObject
  ) => {
    event.preventDefault();
    setSelectedMetadataObject(obj);
    setMetadataMenuAnchor(event.currentTarget);
  };

  const handleMetadataMenuClose = () => {
    setMetadataMenuAnchor(null);
  };

  const handleMetadataInsertSelect = () => {
    if (selectedMetadataObject) {
      handleMetadataSelect(selectedMetadataObject);
    }
    handleMetadataMenuClose();
  };

  const handleMetadataDescribe = () => {
    if (selectedMetadataObject) {
      loadTableMetadata(
        Number(selectedConnection),
        selectedMetadataObject.name,
        selectedMetadataObject.schema || ""
      );
    }
    handleMetadataMenuClose();
  };

  const availableSchemas = useMemo(() => allSchemas, [allSchemas]);

  const filteredMetadataBySchema = useMemo(() => {
    const q = metadataFilter.toLowerCase();
    const result: Record<string, MetadataObject[]> = {};
    availableSchemas.forEach((schema) => {
      const items = metadataBySchema[schema] || [];
      result[schema] = q
        ? items.filter(
            (m) =>
              m.name.toLowerCase().includes(q) ||
              (m.type || "").toLowerCase().includes(q)
          )
        : items;
    });
    return result;
  }, [availableSchemas, metadataBySchema, metadataFilter]);

  const handleTreeExpansion = useCallback(
    async (_event: React.SyntheticEvent, itemIds: string[]) => {
      const newlyExpanded = itemIds.filter((id) => !expandedItems.includes(id));
      setExpandedItems(itemIds);
      for (const id of newlyExpanded) {
        if (allSchemas.includes(id)) {
          if (selectedConnection) {
            await loadMetadataForSchema(Number(selectedConnection), id);
          }
        } else {
          const parts = id.split(":");
          if (parts.length === 3 && parts[1] === "table") {
            const schema = parts[0];
            const table = parts[2];
            await loadTableDetails(schema, table);
          }
        }
      }
    },
    [
      allSchemas,
      expandedItems,
      loadMetadataForSchema,
      selectedConnection,
      loadTableDetails,
    ]
  );

  const groupedByType = useCallback((items: MetadataObject[]) => {
    const groups: Record<string, MetadataObject[]> = {};
    items.forEach((item) => {
      const key = item.type || "other";
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    });
    return groups;
  }, []);

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

      // Set initial value
      editor.setValue(queryTabs[activeTab].query);

      // Update query on change
      editor.onDidChangeModelContent(() => {
        const value = editor.getValue();
        setQueryTabs((prev) =>
          prev.map((tab, index) =>
            index === activeTab ? { ...tab, query: value } : tab
          )
        );
      });
    },
    [registerCompletionProvider, queryTabs, activeTab]
  );

  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.setValue(queryTabs[activeTab].query);
    }
  }, [activeTab, queryTabs]);

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
      setAllSchemas([]);
      setMetadataBySchema({});
      loadSchemas(Number(selectedConnection));
    }
  }, [selectedConnection, loadSchemas]);

  useEffect(() => {
    if (selectedConnection && allSchemas.length > 0) {
      allSchemas.forEach((schema) => {
        if (!metadataBySchema[schema]) {
          loadMetadataForSchema(Number(selectedConnection), schema);
        }
      });
    }
  }, [selectedConnection, allSchemas, loadMetadataForSchema, metadataBySchema]);

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
      <Stack direction="row" spacing={2} alignItems="center">
        <Typography variant="h4">Query browser</Typography>
      </Stack>

      <Menu
        anchorEl={metadataMenuAnchor}
        open={Boolean(metadataMenuAnchor)}
        onClose={handleMetadataMenuClose}
      >
        <MenuItem onClick={handleMetadataInsertSelect}>
          Insert SELECT *
        </MenuItem>
        <MenuItem onClick={handleMetadataDescribe}>Describe table</MenuItem>
      </Menu>

      <Stack direction="row" spacing={2} sx={{ flex: 1, minHeight: 0 }}>
        <Paper
          variant="outlined"
          sx={{
            width: 160,
            minWidth: 140,
            maxWidth: 180,
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          <Stack direction="row" alignItems="center" spacing={1} p={1.5}>
            <Typography variant="subtitle1">Objects</Typography>
            {metadataLoadingSchema && (
              <CircularProgress size={14} sx={{ ml: 1 }} />
            )}
          </Stack>
          <Box px={1.5} pb={1}>
            <TextField
              size="small"
              fullWidth
              placeholder="Filter objects"
              value={metadataFilter}
              onChange={(e) => setMetadataFilter(e.target.value)}
            />
          </Box>
          <Divider />
          <Box sx={{ flex: 1, overflow: "auto" }}>
            {allSchemas.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                {selectedConnection
                  ? "Loading schemas..."
                  : "Choose a connection"}
              </Typography>
            ) : (
              <TreeView
                slots={{
                  collapseIcon: ExpandMoreIcon,
                  expandIcon: ArrowDropDownIcon,
                }}
                expandedItems={expandedItems}
                onExpandedItemsChange={handleTreeExpansion}
              >
                {availableSchemas.map((schema) => {
                  const items = filteredMetadataBySchema[schema] || [];
                  const grouped = groupedByType(items);
                  return (
                    <TreeItem
                      itemId={schema}
                      key={schema}
                      label={
                        <Stack
                          direction="row"
                          spacing={0.75}
                          alignItems="center"
                        >
                          <Typography variant="body2">{schema}</Typography>
                          {metadataLoadingSchema === schema && (
                            <CircularProgress size={12} />
                          )}
                          <Chip
                            size="small"
                            variant="outlined"
                            label={`${items.length} objs`}
                          />
                        </Stack>
                      }
                    >
                      {Object.entries(grouped).map(([type, objs]) => (
                        <TreeItem
                          itemId={`${schema}:${type}`}
                          key={`${schema}:${type}`}
                          label={
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {type}
                            </Typography>
                          }
                        >
                          {objs.map((obj) => {
                            if (obj.type === "table") {
                              const details =
                                tableDetailsBySchemaAndTable[
                                  obj.schema || ""
                                ]?.[obj.name];
                              const loading =
                                tableDetailsLoading ===
                                `${obj.schema || ""}.${obj.name}`;
                              return (
                                <TreeItem
                                  itemId={`${obj.schema || ""}:table:${
                                    obj.name
                                  }`}
                                  key={`${obj.schema || ""}:table:${obj.name}`}
                                  label={
                                    <Stack
                                      direction="row"
                                      spacing={0.5}
                                      alignItems="center"
                                    >
                                      <Typography variant="body2">
                                        {obj.name}
                                      </Typography>
                                      {loading && (
                                        <CircularProgress size={10} />
                                      )}
                                    </Stack>
                                  }
                                  onClick={() => handleMetadataSelect(obj)}
                                  onContextMenu={(e) =>
                                    handleMetadataContextMenu(
                                      e as React.MouseEvent<HTMLElement>,
                                      obj
                                    )
                                  }
                                >
                                  {details && (
                                    <>
                                      <TreeItem
                                        itemId={`${obj.schema || ""}:table:${
                                          obj.name
                                        }:columns`}
                                        label="Columns"
                                      >
                                        {Object.keys(details.columns || {}).map(
                                          (col) => (
                                            <TreeItem
                                              key={col}
                                              itemId={`${
                                                obj.schema || ""
                                              }:table:${
                                                obj.name
                                              }:columns:${col}`}
                                              label={col}
                                            />
                                          )
                                        )}
                                      </TreeItem>
                                      <TreeItem
                                        itemId={`${obj.schema || ""}:table:${
                                          obj.name
                                        }:pks`}
                                        label="Primary Keys"
                                      >
                                        {(details.primary_keys || []).map(
                                          (pk) => (
                                            <TreeItem
                                              key={pk}
                                              itemId={`${
                                                obj.schema || ""
                                              }:table:${obj.name}:pks:${pk}`}
                                              label={pk}
                                            />
                                          )
                                        )}
                                      </TreeItem>
                                      <TreeItem
                                        itemId={`${obj.schema || ""}:table:${
                                          obj.name
                                        }:fks`}
                                        label="Foreign Keys"
                                      >
                                        {(details.foreign_keys || []).map(
                                          (fk, idx) => (
                                            <TreeItem
                                              key={idx}
                                              itemId={`${
                                                obj.schema || ""
                                              }:table:${obj.name}:fks:${idx}`}
                                              label={`${fk.referenced_table}.${fk.referenced_column}`}
                                            />
                                          )
                                        )}
                                      </TreeItem>
                                    </>
                                  )}
                                </TreeItem>
                              );
                            } else {
                              return (
                                <TreeItem
                                  itemId={`${obj.schema || ""}:${obj.type}:${
                                    obj.name
                                  }`}
                                  key={`${obj.schema || ""}:${obj.type}:${
                                    obj.name
                                  }`}
                                  label={
                                    <Typography variant="body2">
                                      {obj.name}
                                    </Typography>
                                  }
                                  onClick={() => handleMetadataSelect(obj)}
                                  onContextMenu={(e) =>
                                    handleMetadataContextMenu(
                                      e as React.MouseEvent<HTMLElement>,
                                      obj
                                    )
                                  }
                                />
                              );
                            }
                          })}
                        </TreeItem>
                      ))}
                      {items.length === 0 && (
                        <TreeItem
                          itemId={`${schema}:empty`}
                          label={
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {metadataLoadingSchema === schema
                                ? "Loading..."
                                : "No objects"}
                            </Typography>
                          }
                        />
                      )}
                    </TreeItem>
                  );
                })}
              </TreeView>
            )}
          </Box>
          {tableMetadata && (
            <>
              <Divider />
              <Box sx={{ p: 1.5, maxHeight: 200, overflow: "auto" }}>
                <Typography variant="subtitle2" gutterBottom>
                  {tableMetadata.schema_name}.{tableMetadata.table_name}
                </Typography>
                <Stack
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  sx={{ pb: 1 }}
                >
                  <Typography variant="caption" color="text.secondary">
                    PK: {tableMetadata.primary_keys.join(", ") || "—"}
                  </Typography>
                  {tableMetadataLoading && (
                    <CircularProgress size={12} color="inherit" />
                  )}
                </Stack>
                <List dense>
                  {Object.keys(tableMetadata.columns || {}).map((col) => (
                    <ListItemButton key={col} disableRipple>
                      <Typography variant="body2">{col}</Typography>
                    </ListItemButton>
                  ))}
                </List>
              </Box>
            </>
          )}
        </Paper>

        <Box
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 2,
            minHeight: 0,
            borderLeft: 1,
            borderColor: "divider",
          }}
        >
          <Tabs
            value={activeTab}
            onChange={(_, newValue) => setActiveTab(newValue)}
          >
            {queryTabs.map((tab) => (
              <Tab key={tab.id} label={tab.title} />
            ))}
          </Tabs>

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
              <Button variant="outlined" onClick={handleNewQueryTab}>
                New Query
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
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                sx={{ flex: 1, justifyContent: "flex-end" }}
              >
                <FormControl size="small" sx={{ minWidth: 220 }}>
                  <InputLabel>Database Connection</InputLabel>
                  <Select
                    label="Database Connection"
                    value={selectedConnection}
                    onChange={(e) =>
                      handleConnectionChange(e.target.value as number | "")
                    }
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
                <Chip label="⌘ / Ctrl + Enter to run" variant="outlined" />
              </Stack>
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
              <Typography variant="subtitle1">Result</Typography>
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
              ) : !queryTabs[activeTab].result ? (
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
              ) : (
                <Box key={queryTabs[activeTab].id} sx={{ p: 2 }}>
                  {queryTabs[activeTab].result!.error ? (
                    <Alert severity="error">
                      {queryTabs[activeTab].result!.error}
                    </Alert>
                  ) : queryTabs[activeTab].result!.rows &&
                    queryTabs[activeTab].result!.rows.length > 0 ? (
                    <DataGrid
                      rows={queryTabs[activeTab].result!.rows.map(
                        (row, idx) => {
                          const rowObj: Record<string, any> = { id: idx };
                          queryTabs[activeTab].result!.columns!.forEach(
                            (col, colIdx) => {
                              rowObj[col] = row[colIdx];
                            }
                          );
                          return rowObj;
                        }
                      )}
                      columns={
                        queryTabs[activeTab].result!.columns?.map((column) => ({
                          field: column,
                          headerName: column,
                          flex: 1,
                          minWidth: 140,
                        })) || []
                      }
                      density="compact"
                      disableRowSelectionOnClick
                      sx={{ border: "none", height: 400 }}
                    />
                  ) : (
                    <Alert severity="info">
                      Query executed successfully. No rows returned.
                    </Alert>
                  )}
                </Box>
              )}
            </Box>
          </Paper>
        </Box>
      </Stack>

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
