import React, { useState, useEffect, useMemo } from "react";
import { FixedSizeList, ListChildComponentProps } from "react-window";
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  CircularProgress,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  IconButton,
  Alert,
  Snackbar,
  Stack,
  LinearProgress,
  Autocomplete,
  Checkbox,
  FormControlLabel,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  TableChart as TableIcon,
  Edit as EditIcon,
  Search as SearchIcon,
} from "@mui/icons-material";
import {
  Connection,
  TableConfig,
  Schema,
  Table as DBTable,
  connectionApi,
  tableApi,
} from "../services/api";

const Tables: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tableConfigs, setTableConfigs] = useState<TableConfig[]>([]);
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [tables, setTables] = useState<DBTable[]>([]);
  const [loadingSchemas, setLoadingSchemas] = useState(false);
  const [loadingTables, setLoadingTables] = useState(false);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [editingTable, setEditingTable] = useState<TableConfig | null>(null);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({
    open: false,
    message: "",
    severity: "success",
  });
  const [formData, setFormData] = useState<Partial<TableConfig>>({
    table_name: "",
    schema_name: "",
    operation_type: "all",
    operation_delay: 1,
    batch_size: 1,
    enabled: true,
    connection_id: 0,
  });
  const [selectedConnection, setSelectedConnection] =
    useState<Connection | null>(null);
  const [connectionError, setConnectionError] = useState<{
    connectionId: number | null;
    message: string;
  } | null>(null);
  const [connectionFilter, setConnectionFilter] = useState<"all" | number>(
    "all",
  );
  const [schemaFilter, setSchemaFilter] = useState("");
  const [tableFilter, setTableFilter] = useState("");
  const [selectedTableNames, setSelectedTableNames] = useState<string[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [connectionsData, tablesData] = await Promise.all([
        connectionApi.list(),
        tableApi.list(),
      ]);
      console.log("✅ Initial data loaded:", {
        connectionsCount: connectionsData?.length || 0,
        tableConfigsCount: tablesData?.length || 0,
      });
      setConnections(connectionsData);
      setTableConfigs(tablesData);
    } catch (error) {
      console.error("Failed to load initial data:", error);
      showSnackbar("Failed to load data", "error");
    } finally {
      setLoading(false);
    }
  };

  const showSnackbar = (message: string, severity: "success" | "error") => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleOpenDialog = () => {
    setFormData({
      table_name: "",
      schema_name: "",
      operation_type: "all",
      operation_delay: 1,
      batch_size: 1,
      enabled: true,
      connection_id: 0,
    });
    setSelectedConnection(null);
    setSchemas([]);
    setTables([]);
    setSchemaFilter("");
    setTableFilter("");
    setSelectedTableNames([]);
    setOpen(true);
  };

  const handleCloseDialog = () => {
    setOpen(false);
    setEditingTable(null);
    setFormData({
      table_name: "",
      schema_name: "",
      operation_delay: 1,
      batch_size: 1,
      enabled: true,
      connection_id: 0,
    });
    setSelectedConnection(null);
    setSchemas([]);
    setTables([]);
    setSchemaFilter("");
    setTableFilter("");
    setSelectedTableNames([]);
  };

  const handleConnectionChange = async (connectionId: number) => {
    const connection = (Array.isArray(connections) ? connections : []).find(
      (c) => c.id === connectionId,
    );
    if (!connection) return;

    // Reset error state for this connection
    setConnectionError(null);
    setSelectedConnection(connection);
    setFormData((prev) => ({ ...prev, connection_id: connectionId }));

    console.log("🔄 Starting to load schemas for connection:", connectionId);
    setLoadingSchemas(true);

    try {
      const schemasData = await connectionApi.getSchemas(connectionId);
      console.log(
        "✅ Schemas loaded successfully:",
        schemasData?.length || 0,
        "schemas found",
      );
      // Convert string array to Schema objects for frontend compatibility
      const schemaObjects = schemasData.map((schema: string) => ({
        name: schema,
      }));
      setSchemas(schemaObjects);
    } catch (error: any) {
      console.error("Failed to load schemas:", error);
      const errorMessage =
        error?.response?.data?.detail ||
        error?.message ||
        "Failed to load schemas";

      // Set connection error state
      if (
        errorMessage.includes("Connection refused") ||
        errorMessage.includes("Not connected to database") ||
        errorMessage.includes("Connection timed out") ||
        errorMessage.includes("authentication failed")
      ) {
        setConnectionError({
          connectionId,
          message: `Cannot connect to database "${
            connection?.name || "Unknown"
          }". Please check connection settings.`,
        });
      } else {
        setConnectionError({
          connectionId,
          message: `Failed to load schemas: ${errorMessage}`,
        });
      }

      setSchemas([]);
      showSnackbar(
        connectionError?.message || "Failed to load schemas",
        "error",
      );
    } finally {
      setLoadingSchemas(false);
    }
  };

  const handleSchemaChange = async (schemaName: string) => {
    if (!selectedConnection) return;

    setFormData((prev) => ({ ...prev, schema_name: schemaName }));
    setTableFilter("");
    setSelectedTableNames([]);
    setTables([]);

    setLoadingTables(true);
    try {
      const tablesData = await connectionApi.getTables(
        selectedConnection.id!,
        schemaName,
      );
      setTables(tablesData);
    } catch (error: any) {
      console.error("Failed to load tables:", error);
      const errorMessage =
        error?.response?.data?.detail ||
        error?.message ||
        "Failed to load tables";

      // Check if it's a connection error
      if (
        errorMessage.includes("Connection refused") ||
        errorMessage.includes("Not connected to database")
      ) {
        showSnackbar(
          `Cannot connect to database "${selectedConnection.name}". Please check connection settings.`,
          "error",
        );
      } else {
        showSnackbar(`Failed to load tables: ${errorMessage}`, "error");
      }

      setTables([]);
    } finally {
      setLoadingTables(false);
    }
  };

  const handleInputChange = (field: keyof TableConfig, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    if (!formData.schema_name || !formData.connection_id) {
      showSnackbar("Please fill in all required fields", "error");
      return;
    }

    try {
      if (editingTable) {
        if (!formData.table_name) {
          showSnackbar("Please select a table", "error");
          return;
        }
        const payload: TableConfig = {
          ...(formData as TableConfig),
          operation_type: formData.operation_type ?? "all",
        };
        await tableApi.update(editingTable.id!, payload);
        showSnackbar("Table configuration updated successfully", "success");
      } else {
        const tablesToCreate =
          selectedTableNames.length > 0
            ? selectedTableNames
            : formData.table_name
              ? [formData.table_name]
              : [];

        if (tablesToCreate.length === 0) {
          showSnackbar("Please select at least one table", "error");
          return;
        }

        const configs: TableConfig[] = tablesToCreate.map((tableName) => ({
          ...(formData as TableConfig),
          table_name: tableName,
          operation_type: formData.operation_type ?? "all",
        }));

        await tableApi.batchCreate(configs);
        showSnackbar(
          `${tablesToCreate.length} table configuration(s) created successfully`,
          "success",
        );
      }
      handleCloseDialog();
      loadData();
    } catch (error) {
      const action = editingTable ? "update" : "create";
      showSnackbar(`Failed to ${action} table configuration`, "error");
    }
  };

  const handleDelete = async (id: number) => {
    if (
      window.confirm(
        "Are you sure you want to delete this table configuration?",
      )
    ) {
      try {
        await tableApi.delete(id);
        showSnackbar("Table configuration deleted successfully", "success");
        loadData();
      } catch (error) {
        showSnackbar("Failed to delete table configuration", "error");
      }
    }
  };

  const handleEdit = async (tableConfig: TableConfig) => {
    setEditingTable(tableConfig);
    setFormData({
      table_name: tableConfig.table_name,
      schema_name: tableConfig.schema_name,
      operation_type: tableConfig.operation_type ?? "all",
      operation_delay: tableConfig.operation_delay,
      batch_size: tableConfig.batch_size,
      enabled: tableConfig.enabled,
      connection_id: tableConfig.connection_id,
    });
    setSelectedTableNames([tableConfig.table_name]);
    setSchemaFilter("");
    setTableFilter("");

    // Load the connection and its schemas
    const connection = (Array.isArray(connections) ? connections : []).find(
      (c) => c.id === tableConfig.connection_id,
    );
    if (connection) {
      setSelectedConnection(connection);

      try {
        // Load schemas for the connection
        const schemasData = await connectionApi.getSchemas(connection.id!);
        const schemaObjects = schemasData.map((schema: string) => ({
          name: schema,
        }));
        setSchemas(schemaObjects);

        // Load tables for the schema
        const tablesData = await connectionApi.getTables(
          connection.id!,
          tableConfig.schema_name,
        );
        setTables(tablesData);
      } catch (error: any) {
        console.error("Failed to load data for editing:", error);
        const errorMessage =
          error?.response?.data?.detail ||
          error?.message ||
          "Failed to load data for editing";

        // Check if it's a connection error
        if (
          errorMessage.includes("Connection refused") ||
          errorMessage.includes("Not connected to database")
        ) {
          showSnackbar(
            `Cannot connect to database "${connection.name}". Please check connection settings.`,
            "error",
          );
        } else {
          showSnackbar(
            `Failed to load data for editing: ${errorMessage}`,
            "error",
          );
        }

        // Still open the dialog but with empty schemas/tables
        setSchemas([]);
        setTables([]);
      }
    }

    setOpen(true);
  };

  const connectionLookup = useMemo(() => {
    const map: Record<number, Connection> = {};
    (Array.isArray(connections) ? connections : []).forEach((connection) => {
      if (connection.id != null) {
        map[connection.id] = connection;
      }
    });
    return map;
  }, [connections]);

  const filteredTableConfigs = useMemo(() => {
    const configs = Array.isArray(tableConfigs) ? tableConfigs : [];
    if (connectionFilter === "all") {
      return configs;
    }
    return configs.filter(
      (config) => config.connection_id === Number(connectionFilter),
    );
  }, [tableConfigs, connectionFilter]);

  const groupedTableConfigs = useMemo(() => {
    const groups: Record<number, TableConfig[]> = {};
    filteredTableConfigs.forEach((config) => {
      const key = config.connection_id;
      if (!groups[key]) {
        groups[key] = [];
      }
      groups[key].push(config);
    });
    return groups;
  }, [filteredTableConfigs]);

  const connectionColorMap = useMemo(() => {
    const palette = [
      "primary",
      "secondary",
      "success",
      "info",
      "warning",
      "default",
    ] as const;
    const map: Record<number, (typeof palette)[number]> = {};
    (Array.isArray(connections) ? connections : []).forEach(
      (connection, index) => {
        if (connection.id != null) {
          map[connection.id] = palette[index % palette.length];
        }
      },
    );
    return map;
  }, [connections]);

  const filteredSchemas = useMemo(() => {
    const all = Array.isArray(schemas) ? schemas : [];
    if (!schemaFilter.trim()) return all;
    const lower = schemaFilter.toLowerCase();
    return all.filter((s) =>
      (typeof s === "string" ? s : s.name).toLowerCase().includes(lower),
    );
  }, [schemas, schemaFilter]);

  const filteredTables = useMemo(() => {
    const all = Array.isArray(tables) ? tables : [];
    if (!tableFilter.trim()) return all;
    const lower = tableFilter.toLowerCase();
    return all.filter((t) => t.name.toLowerCase().includes(lower));
  }, [tables, tableFilter]);

  const connectionFilterChips = (
    <Stack direction="row" spacing={1} flexWrap="wrap" mb={2} rowGap={1}>
      <Chip
        label="All connections"
        color={connectionFilter === "all" ? "primary" : "default"}
        variant={connectionFilter === "all" ? "filled" : "outlined"}
        onClick={() => setConnectionFilter("all")}
      />
      {(Array.isArray(connections) ? connections : []).map((connection) => {
        if (connection.id == null) {
          return null;
        }
        const isSelected = connectionFilter === connection.id;
        return (
          <Chip
            key={`filter-chip-${connection.id}`}
            label={connection.name}
            color={isSelected ? "primary" : "default"}
            variant={isSelected ? "filled" : "outlined"}
            onClick={() => setConnectionFilter(connection.id!)}
          />
        );
      })}
    </Stack>
  );

  const renderGroupedRows = () => {
    const entries = Object.entries(groupedTableConfigs);
    if (entries.length === 0) {
      return (
        <TableRow>
          <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
            <Typography variant="body2" color="text.secondary">
              {connectionFilter === "all"
                ? "No table configurations found. Configure your first table to get started."
                : "No table configurations match the selected connection filter."}
            </Typography>
          </TableCell>
        </TableRow>
      );
    }

    return entries.map(([connectionId, configs]) => {
      const numericId = Number(connectionId);
      const connection = connectionLookup[numericId];
      const connectionColor = connectionColorMap[numericId] ?? "default";

      return (
        <React.Fragment key={`group-${connectionId}`}>
          <TableRow sx={{ backgroundColor: "grey.50" }}>
            <TableCell colSpan={5}>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={1}
                alignItems={{ xs: "flex-start", sm: "center" }}
                justifyContent="space-between"
              >
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="subtitle1" fontWeight="bold">
                    {connection?.name || "Unknown Connection"}
                  </Typography>
                  {connection?.db_type && (
                    <Chip
                      label={connection.db_type.toUpperCase()}
                      size="small"
                      color={connectionColor}
                      variant="outlined"
                    />
                  )}
                </Stack>
                {connection && (
                  <Typography variant="body2" color="text.secondary">
                    {connection.host}:{connection.port}
                  </Typography>
                )}
              </Stack>
            </TableCell>
          </TableRow>
          {configs.map((config) => (
            <TableRow key={config.id}>
              <TableCell>
                <Stack spacing={0.5}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <TableIcon sx={{ color: "primary.main" }} />
                    <Typography variant="body1" fontWeight="medium">
                      {config.table_name}
                    </Typography>
                  </Stack>
                  <Chip
                    label={connection?.name || "Unknown"}
                    size="small"
                    color={connectionColor}
                    variant="outlined"
                    sx={{ alignSelf: "flex-start" }}
                  />
                </Stack>
              </TableCell>
              <TableCell>{config.schema_name}</TableCell>
              <TableCell>
                <Typography variant="body2">
                  Delay: {config.operation_delay}s
                </Typography>
                <Typography variant="body2">
                  Batch: {config.batch_size}
                </Typography>
              </TableCell>
              <TableCell>
                <Chip
                  label={config.enabled ? "Enabled" : "Disabled"}
                  size="small"
                  color={config.enabled ? "success" : "warning"}
                />
              </TableCell>
              <TableCell align="right">
                <IconButton
                  size="small"
                  onClick={() => handleEdit(config)}
                  color="primary"
                >
                  <EditIcon />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => handleDelete(config.id!)}
                  color="error"
                >
                  <DeleteIcon />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </React.Fragment>
      );
    });
  };

  return (
    <Box>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 3,
        }}
      >
        <Typography variant="h4">Table configurations</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleOpenDialog}
          disabled={connections.length === 0}
        >
          Configure table
        </Button>
      </Box>

      {connections.length === 0 && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          No database connections available. Please create a connection first
          before configuring tables.
        </Alert>
      )}

      {connections.length > 0 && connectionFilterChips}

      <Card>
        <CardContent>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Table Name</TableCell>
                  <TableCell>Schema</TableCell>
                  <TableCell>Settings</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              {loading && (
                <TableBody>
                  <TableRow>
                    <TableCell colSpan={5} sx={{ p: 0 }}>
                      <LinearProgress />
                    </TableCell>
                  </TableRow>
                </TableBody>
              )}
              <TableBody>{renderGroupedRows()}</TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Configure Table Dialog */}
      <Dialog open={open} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingTable
            ? "Edit Table Configuration"
            : "Configure Table for Automation"}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
            {loadingSchemas ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
                <CircularProgress size={24} />
              </Box>
            ) : connectionError?.connectionId === formData.connection_id ? (
              <Alert severity="error" sx={{ mb: 1 }}>
                {connectionError?.message ?? ""}
              </Alert>
            ) : null}

            <FormControl fullWidth>
              <InputLabel>Connection</InputLabel>
              <Select
                value={formData.connection_id || ""}
                label="Connection"
                onChange={(e) => {
                  const value = e.target.value;
                  handleConnectionChange(
                    typeof value === "string" ? parseInt(value, 10) : value,
                  );
                }}
              >
                {(Array.isArray(connections) ? connections : []).map(
                  (connection) => (
                    <MenuItem
                      key={`connection-${connection.id || connection.name}`}
                      value={connection.id?.toString() || ""}
                    >
                      {connection.name} ({connection.db_type})
                    </MenuItem>
                  ),
                )}
              </Select>
            </FormControl>

            {schemas.length > 0 && (
              <Autocomplete
                options={filteredSchemas}
                getOptionLabel={(option) =>
                  typeof option === "string" ? option : option.name
                }
                value={
                  formData.schema_name
                    ? schemas.find(
                        (s) =>
                          (typeof s === "string" ? s : s.name) ===
                          formData.schema_name,
                      ) || null
                    : null
                }
                onChange={(_event, newValue) => {
                  if (newValue) {
                    handleSchemaChange(
                      typeof newValue === "string" ? newValue : newValue.name,
                    );
                  }
                }}
                inputValue={schemaFilter}
                onInputChange={(_event, newInputValue) => {
                  setSchemaFilter(newInputValue);
                }}
                renderInput={(params) => (
                  <TextField {...params} label="Schema" variant="outlined" />
                )}
                fullWidth
                clearOnEscape
              />
            )}

            {loadingTables && (
              <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
                <CircularProgress size={24} />
              </Box>
            )}

            {!loadingTables && tables.length > 0 && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  {editingTable ? "Table" : "Tables"}
                </Typography>
                {!editingTable && (
                  <>
                    <TextField
                      placeholder="Search tables..."
                      value={tableFilter}
                      onChange={(e) => setTableFilter(e.target.value)}
                      fullWidth
                      size="small"
                      sx={{ mb: 1 }}
                      InputProps={{
                        startAdornment: (
                          <SearchIcon sx={{ mr: 1, color: "text.secondary" }} />
                        ),
                      }}
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={
                            filteredTables.length > 0 &&
                            filteredTables.every((t) =>
                              selectedTableNames.includes(t.name),
                            )
                          }
                          indeterminate={
                            filteredTables.some((t) =>
                              selectedTableNames.includes(t.name),
                            ) &&
                            !filteredTables.every((t) =>
                              selectedTableNames.includes(t.name),
                            )
                          }
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedTableNames((prev) => {
                                const filteredNames = filteredTables.map(
                                  (t) => t.name,
                                );
                                return Array.from(
                                  new Set([...prev, ...filteredNames]),
                                );
                              });
                            } else {
                              setSelectedTableNames((prev) =>
                                prev.filter(
                                  (name) =>
                                    !filteredTables.some(
                                      (t) => t.name === name,
                                    ),
                                ),
                              );
                            }
                          }}
                        />
                      }
                      label={`Select All (${filteredTables.length} visible)`}
                      sx={{ mb: 1 }}
                    />
                  </>
                )}
                <Paper variant="outlined">
                  {filteredTables.length === 0 ? (
                    <Box sx={{ p: 2, textAlign: "center" }}>
                      <Typography variant="body2" color="text.secondary">
                        No tables match your search
                      </Typography>
                    </Box>
                  ) : editingTable ? (
                    <FixedSizeList
                      height={240}
                      itemCount={filteredTables.length}
                      itemSize={40}
                      width="100%"
                    >
                      {({ index, style }: ListChildComponentProps) => {
                        const table = filteredTables[index];
                        return (
                          <ListItemButton
                            key={`table-${table.name}`}
                            style={style}
                            selected={formData.table_name === table.name}
                            onClick={() =>
                              handleInputChange("table_name", table.name)
                            }
                          >
                            <ListItemText primary={table.name} />
                          </ListItemButton>
                        );
                      }}
                    </FixedSizeList>
                  ) : (
                    <FixedSizeList
                      height={240}
                      itemCount={filteredTables.length}
                      itemSize={40}
                      width="100%"
                    >
                      {({ index, style }: ListChildComponentProps) => {
                        const table = filteredTables[index];
                        return (
                          <ListItemButton
                            key={`table-${table.name}`}
                            style={style}
                            onClick={() => {
                              setSelectedTableNames((prev) =>
                                prev.includes(table.name)
                                  ? prev.filter((n) => n !== table.name)
                                  : [...prev, table.name],
                              );
                            }}
                          >
                            <ListItemIcon sx={{ minWidth: 36 }}>
                              <Checkbox
                                edge="start"
                                checked={selectedTableNames.includes(table.name)}
                                tabIndex={-1}
                                disableRipple
                              />
                            </ListItemIcon>
                            <ListItemText primary={table.name} />
                          </ListItemButton>
                        );
                      }}
                    </FixedSizeList>
                  )}
                </Paper>
                {!editingTable && selectedTableNames.length > 0 && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ mt: 0.5, display: "block" }}
                  >
                    {selectedTableNames.length} table(s) selected
                  </Typography>
                )}
              </Box>
            )}

            <Box sx={{ display: "flex", gap: 2 }}>
              <Box sx={{ flex: "1 1 50%" }}>
                <TextField
                  label="Delay (seconds)"
                  type="number"
                  value={formData.operation_delay}
                  onChange={(e) =>
                    handleInputChange(
                      "operation_delay",
                      parseFloat(e.target.value) || 1,
                    )
                  }
                  fullWidth
                  inputProps={{ min: 0.1, step: 0.1 }}
                />
              </Box>
              <Box sx={{ flex: "1 1 50%" }}>
                <TextField
                  label="Batch Size"
                  type="number"
                  value={formData.batch_size}
                  onChange={(e) =>
                    handleInputChange(
                      "batch_size",
                      parseInt(e.target.value) || 1,
                    )
                  }
                  fullWidth
                  inputProps={{ min: 1 }}
                />
              </Box>
            </Box>

            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={formData.enabled ? "enabled" : "disabled"}
                label="Status"
                onChange={(e) =>
                  handleInputChange("enabled", e.target.value === "enabled")
                }
              >
                <MenuItem value="enabled">Enabled</MenuItem>
                <MenuItem value="disabled">Disabled</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={
              (!editingTable &&
                selectedTableNames.length === 0 &&
                !formData.table_name) ||
              (editingTable && !formData.table_name) ||
              !formData.schema_name ||
              !formData.connection_id
            }
          >
            {editingTable
              ? "Update Configuration"
              : selectedTableNames.length > 1
                ? `Configure ${selectedTableNames.length} Tables`
                : "Configure Table"}
          </Button>
        </DialogActions>
      </Dialog>

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

export default Tables;
