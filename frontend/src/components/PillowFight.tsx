import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormHelperText,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  List,
  ListItem,
  ListItemSecondaryAction,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
  Checkbox,
} from "@mui/material";
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
} from "@mui/icons-material";
import {
  Connection,
  TableConfig,
  PillowFightJobStatus,
  PillowFightJobRequest,
  pillowFightApi,
  connectionApi,
  tableApi,
} from "../services/api";

const STATUS_COLORS: Record<
  string,
  "default" | "success" | "warning" | "error" | "info"
> = {
  pending: "warning",
  running: "success",
  completed: "default",
  stopped: "default",
  error: "error",
};

const getStatusColor = (status?: string) =>
  STATUS_COLORS[status?.toLowerCase() || ""] ?? "default";

const OPERATION_KEYS = ["insert", "update", "delete"] as const;
type OperationKey = (typeof OPERATION_KEYS)[number];

const PillowFight: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tableConfigs, setTableConfigs] = useState<TableConfig[]>([]);
  const [jobs, setJobs] = useState<PillowFightJobStatus[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [loadingData, setLoadingData] = useState(false);

  const [jobSearchInput, setJobSearchInput] = useState("");
  const [jobSearch, setJobSearch] = useState("");

  const [startDialogOpen, setStartDialogOpen] = useState(false);
  const [selectedConnection, setSelectedConnection] = useState<number | "">("");
  const [tableSearch, setTableSearch] = useState("");
  const [selectedTables, setSelectedTables] = useState<number[]>([]);
  const [operationSelections, setOperationSelections] = useState<
    Record<OperationKey, boolean>
  >({
    insert: true,
    update: true,
    delete: true,
  });
  const [operationDelay, setOperationDelay] = useState(1);
  const [batchSize, setBatchSize] = useState(1);
  const [actionInFlight, setActionInFlight] = useState<string | null>(null);

  useEffect(() => {
    loadInitialData();
    loadJobs();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      loadJobs();
    }, 4000);
    return () => clearInterval(interval);
  }, [jobSearch]);

  const loadInitialData = async () => {
    try {
      setLoadingData(true);
      const [connectionsData, tablesData] = await Promise.all([
        connectionApi.list(),
        tableApi.list(),
      ]);
      setConnections(connectionsData);
      setTableConfigs(tablesData);
    } catch (error) {
      console.error("Failed to load connections or tables", error);
    } finally {
      setLoadingData(false);
    }
  };

  const loadJobs = async (searchOverride?: string) => {
    try {
      setJobsLoading(true);
      const response = await pillowFightApi.listJobs(
        searchOverride ?? (jobSearch || undefined)
      );
      setJobs(response.jobs);
    } catch (error) {
      console.error("Failed to load pillow fight jobs", error);
    } finally {
      setJobsLoading(false);
    }
  };

  const connectionLookup = useMemo(() => {
    const map = new Map<number, Connection>();
    connections.forEach((connection) => {
      if (connection.id != null) {
        map.set(connection.id, connection);
      }
    });
    return map;
  }, [connections]);

  const availableTables = useMemo(() => {
    if (!selectedConnection) return [];
    return tableConfigs.filter((table) => {
      const matchesConnection = table.connection_id === selectedConnection;
      const matchesSearch = tableSearch
        ? `${table.schema_name}.${table.table_name}`
            .toLowerCase()
            .includes(tableSearch.toLowerCase())
        : true;
      return matchesConnection && matchesSearch;
    });
  }, [selectedConnection, tableConfigs, tableSearch]);

  const handleOpenStartDialog = () => {
    if (connections.length > 0) {
      const defaultConnectionId = connections[0].id ?? "";
      setSelectedConnection(defaultConnectionId);
      const tablesForConnection = tableConfigs
        .filter((table) => table.connection_id === defaultConnectionId)
        .map((table) => table.id!)
        .filter((id): id is number => Boolean(id));
      setSelectedTables(tablesForConnection);
    }
    setTableSearch("");
    setStartDialogOpen(true);
  };

  const handleToggleTable = (tableId: number) => {
    setSelectedTables((prev) =>
      prev.includes(tableId)
        ? prev.filter((id) => id !== tableId)
        : [...prev, tableId]
    );
  };

  const handleToggleSelectAll = () => {
    const visibleIds = availableTables
      .map((table) => table.id!)
      .filter((id): id is number => Boolean(id));
    const allSelected = visibleIds.every((id) => selectedTables.includes(id));
    if (allSelected) {
      setSelectedTables((prev) =>
        prev.filter((id) => !visibleIds.includes(id))
      );
    } else {
      setSelectedTables((prev) =>
        Array.from(new Set([...prev, ...visibleIds]))
      );
    }
  };

  const selectedOperations = useMemo(
    () => OPERATION_KEYS.filter((key) => operationSelections[key]),
    [operationSelections]
  );

  const handleStartJob = async () => {
    if (!selectedConnection || selectedTables.length === 0) {
      alert("Select a connection and at least one table.");
      return;
    }

    if (selectedOperations.length === 0) {
      alert("Select at least one operation type.");
      return;
    }

    const request: PillowFightJobRequest = {
      connection_id: selectedConnection,
      table_ids: selectedTables,
      operation_types: selectedOperations,
      operation_delay: operationDelay,
      batch_size: batchSize,
    };

    try {
      setActionInFlight("start");
      await pillowFightApi.startJob(request);
      setStartDialogOpen(false);
      await loadJobs();
    } catch (error) {
      console.error("Failed to start pillow fight job", error);
      alert("Failed to start pillow fight job. Check logs for details.");
    } finally {
      setActionInFlight(null);
    }
  };

  const handleStopJob = async (jobId: string) => {
    try {
      setActionInFlight(jobId);
      await pillowFightApi.stopJob(jobId);
      await loadJobs();
    } catch (error) {
      console.error(`Failed to stop pillow fight job ${jobId}`, error);
      alert("Failed to stop job.");
    } finally {
      setActionInFlight(null);
    }
  };

  const handleStopTable = async (jobId: string, tableId: number) => {
    try {
      setActionInFlight(`${jobId}:${tableId}`);
      await pillowFightApi.stopTable(jobId, tableId);
      await loadJobs();
    } catch (error) {
      console.error(`Failed to stop table ${tableId} for job ${jobId}`, error);
      alert("Failed to stop table.");
    } finally {
      setActionInFlight(null);
    }
  };

  const activeTableStatuses = ["pending", "running"];
  const isJobActive = (job: PillowFightJobStatus) =>
    activeTableStatuses.some((status) =>
      job.tables.some((table) => table.status?.toLowerCase() === status)
    ) || ["pending", "running"].includes(job.status?.toLowerCase());

  const handleJobSearch = async () => {
    setJobSearch(jobSearchInput.trim());
    await loadJobs(jobSearchInput.trim());
  };

  const handleJobSearchKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>
  ) => {
    if (event.key === "Enter") {
      handleJobSearch();
    }
  };

  const renderJobCard = (job: PillowFightJobStatus) => {
    const connectionName =
      connectionLookup.get(job.connection_id)?.name || job.connection_id;
    const aggregateCounts = job.tables.reduce(
      (acc, table) => {
        acc.insert += table.insert_count || 0;
        acc.update += table.update_count || 0;
        acc.delete += table.delete_count || 0;
        acc.error += table.error_count || 0;
        return acc;
      },
      { insert: 0, update: 0, delete: 0, error: 0 }
    );

    return (
      <Card key={job.job_id} variant="outlined">
        <CardContent>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            alignItems={{ xs: "flex-start", sm: "center" }}
            justifyContent="space-between"
            spacing={2}
            sx={{ mb: 2 }}
          >
            <Box>
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                sx={{ mb: 1 }}
              >
                <Typography variant="h6">Job {job.job_id}</Typography>
                <Chip
                  label={job.status?.toUpperCase()}
                  color={getStatusColor(job.status)}
                  size="small"
                />
              </Stack>
              <Typography variant="body2" color="text.secondary">
                Connection: <strong>{connectionName}</strong>
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Ops: {job.operation_types.join(", ").toUpperCase()} • Delay:{" "}
                {job.operation_delay}s • Batch: {job.batch_size}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Totals — Insert: {aggregateCounts.insert} • Update:{" "}
                {aggregateCounts.update} • Delete: {aggregateCounts.delete} •
                Errors: {aggregateCounts.error}
              </Typography>
              {job.error_message && (
                <Alert severity="error" sx={{ mt: 1, py: 0 }}>
                  {job.error_message}
                </Alert>
              )}
            </Box>
            <Stack direction="row" spacing={1}>
              <Button
                variant="outlined"
                color="primary"
                startIcon={<RefreshIcon />}
                onClick={() => loadJobs()}
                disabled={jobsLoading}
              >
                Refresh
              </Button>
              <Button
                variant="contained"
                color="error"
                startIcon={<StopIcon />}
                onClick={() => handleStopJob(job.job_id)}
                disabled={!isJobActive(job) || actionInFlight === job.job_id}
              >
                Stop Job
              </Button>
            </Stack>
          </Stack>

          <Divider sx={{ mb: 2 }} />

          {job.tables.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No table executions found for this job.
            </Typography>
          ) : (
            <Stack spacing={1.5}>
              {job.tables.map((table) => {
                const tableActive = activeTableStatuses.includes(
                  table.status?.toLowerCase() || ""
                );
                return (
                  <Box
                    key={`${job.job_id}-${table.table_id}`}
                    sx={{
                      display: "flex",
                      flexDirection: { xs: "column", sm: "row" },
                      justifyContent: "space-between",
                      alignItems: { xs: "flex-start", sm: "center" },
                      gap: 1,
                      p: 1,
                      border: "1px solid",
                      borderColor: "divider",
                      borderRadius: 1,
                    }}
                  >
                    <Box>
                      <Typography variant="subtitle2">
                        {table.table_name || `Table ${table.table_id}`}{" "}
                        <Typography
                          component="span"
                          variant="caption"
                          color="text.secondary"
                        >
                          ({table.schema_name || "unknown schema"})
                        </Typography>
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        ID {table.table_id} • Last Operation:{" "}
                        {table.last_operation_at
                          ? new Date(table.last_operation_at).toLocaleString()
                          : "n/a"}
                      </Typography>
                      <Typography variant="body2">
                        Insert: {table.insert_count} • Update:{" "}
                        {table.update_count} • Delete: {table.delete_count} •
                        Errors: {table.error_count}
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip
                        label={table.status?.toUpperCase()}
                        color={getStatusColor(table.status)}
                        size="small"
                      />
                      <Button
                        size="small"
                        variant="outlined"
                        color="error"
                        startIcon={<StopIcon fontSize="small" />}
                        onClick={() =>
                          handleStopTable(job.job_id, table.table_id)
                        }
                        disabled={
                          !tableActive ||
                          actionInFlight === `${job.job_id}:${table.table_id}`
                        }
                      >
                        Stop Table
                      </Button>
                    </Stack>
                  </Box>
                );
              })}
            </Stack>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <Box>
      <Stack
        direction={{ xs: "column", md: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", md: "center" }}
        spacing={2}
        sx={{ mb: 3 }}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            Pillow fight control
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage multi-table pillow fight jobs, track per-table operations,
            and stop jobs individually.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button
            variant="contained"
            color="success"
            startIcon={<PlayIcon />}
            onClick={handleOpenStartDialog}
            disabled={loadingData || connections.length === 0}
          >
            Start pillow fight
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => loadJobs()}
            disabled={jobsLoading}
          >
            Refresh jobs
          </Button>
        </Stack>
      </Stack>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Overview
              </Typography>
              <Typography variant="body2">
                Connections: {connections.length}
              </Typography>
              <Typography variant="body2">
                Configured Tables: {tableConfigs.length}
              </Typography>
              <Typography variant="body2">
                Tracked Jobs: {jobs.length}
              </Typography>

              {connections.length === 0 && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  No connections configured. Please add a connection first.
                </Alert>
              )}
              {connections.length > 0 && tableConfigs.length === 0 && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  No table configurations available. Configure tables to start
                  pillow fights.
                </Alert>
              )}
            </CardContent>
          </Card>

          <Card sx={{ mt: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Job Search
              </Typography>
              <TextField
                fullWidth
                placeholder="Search by job ID or error text"
                value={jobSearchInput}
                onChange={(e) => setJobSearchInput(e.target.value)}
                onKeyDown={handleJobSearchKeyDown}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton onClick={handleJobSearch}>
                        <SearchIcon />
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          {jobsLoading && (
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
              sx={{ mb: 2 }}
            >
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                Loading jobs...
              </Typography>
            </Stack>
          )}

          {jobs.length === 0 && !jobsLoading ? (
            <Alert severity="info">
              No pillow fight jobs found. Start one to begin tracking.
            </Alert>
          ) : (
            <Stack spacing={2}>{jobs.map((job) => renderJobCard(job))}</Stack>
          )}
        </Grid>
      </Grid>

      <Dialog
        open={startDialogOpen}
        onClose={() => setStartDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Start Pillow Fight Job</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={3}>
            <FormControl fullWidth>
              <InputLabel id="connection-select-label">Connection</InputLabel>
              <Select
                labelId="connection-select-label"
                label="Connection"
                value={selectedConnection}
                onChange={(e) => {
                  const connId = Number(e.target.value);
                  setSelectedConnection(connId);
                  const tablesForConnection = tableConfigs
                    .filter((table) => table.connection_id === connId)
                    .map((table) => table.id!)
                    .filter((id): id is number => Boolean(id));
                  setSelectedTables(tablesForConnection);
                }}
              >
                {connections.map((connection) => (
                  <MenuItem key={connection.id} value={connection.id}>
                    {connection.name} ({connection.db_type})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                justifyContent="space-between"
                alignItems={{ xs: "flex-start", sm: "center" }}
                spacing={2}
                sx={{ mb: 1 }}
              >
                <Box>
                  <Typography variant="subtitle1">
                    Tables ({selectedTables.length} selected)
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Use search to narrow down the list. Select all applies to
                    filtered tables.
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1}>
                  <TextField
                    size="small"
                    placeholder="Search tables"
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                  />
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={handleToggleSelectAll}
                  >
                    Toggle Select All
                  </Button>
                </Stack>
              </Stack>

              {selectedConnection === "" ? (
                <Alert severity="info">
                  Select a connection to view tables.
                </Alert>
              ) : availableTables.length === 0 ? (
                <Alert severity="warning">No tables match your filter.</Alert>
              ) : (
                <List
                  dense
                  sx={{
                    maxHeight: 260,
                    overflow: "auto",
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 1,
                  }}
                >
                  {availableTables.map((table) => (
                    <ListItem key={table.id} disableGutters>
                      <Checkbox
                        edge="start"
                        checked={selectedTables.includes(table.id!)}
                        onChange={() => handleToggleTable(table.id!)}
                      />
                      <ListItemText
                        primary={`${table.table_name} (${table.schema_name})`}
                        secondary={`Delay: ${table.operation_delay}s • Batch: ${table.batch_size}`}
                      />
                      <ListItemSecondaryAction>
                        <Typography variant="caption" color="text.secondary">
                          ID {table.id}
                        </Typography>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>

            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <FormControl component="fieldset" fullWidth>
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    Operation Types
                  </Typography>
                  <FormGroup row>
                    {OPERATION_KEYS.map((op) => (
                      <FormControlLabel
                        key={op}
                        control={
                          <Checkbox
                            checked={operationSelections[op]}
                            onChange={(e) =>
                              setOperationSelections((prev) => ({
                                ...prev,
                                [op]: e.target.checked,
                              }))
                            }
                          />
                        }
                        label={op.charAt(0).toUpperCase() + op.slice(1)}
                      />
                    ))}
                  </FormGroup>
                  {selectedOperations.length === 0 && (
                    <FormHelperText error>
                      Select at least one operation.
                    </FormHelperText>
                  )}
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField
                  label="Delay (seconds)"
                  type="number"
                  value={operationDelay}
                  onChange={(e) =>
                    setOperationDelay(parseFloat(e.target.value) || 1)
                  }
                  fullWidth
                  inputProps={{ min: 0.1, step: 0.1 }}
                />
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField
                  label="Batch Size"
                  type="number"
                  value={batchSize}
                  onChange={(e) =>
                    setBatchSize(parseInt(e.target.value, 10) || 1)
                  }
                  fullWidth
                  inputProps={{ min: 1 }}
                />
              </Grid>
            </Grid>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStartDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleStartJob}
            variant="contained"
            color="success"
            startIcon={<PlayIcon />}
            disabled={
              !selectedConnection ||
              selectedTables.length === 0 ||
              actionInFlight === "start"
            }
          >
            Start Job
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default PillowFight;
