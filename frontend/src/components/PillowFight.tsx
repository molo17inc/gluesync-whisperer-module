import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Chip,
  Alert,
  CircularProgress,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  Checkbox,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import {
  Connection,
  TableConfig,
  PillowFightRequest,
  PillowFightStatus,
  connectionApi,
  tableApi,
  pillowFightApi,
} from '../services/api';

const PillowFight: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tableConfigs, setTableConfigs] = useState<TableConfig[]>([]);
  const [pillowFightStatus, setPillowFightStatus] = useState<PillowFightStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [startDialogOpen, setStartDialogOpen] = useState(false);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [selectedTables, setSelectedTables] = useState<number[]>([]);
  const [operationType, setOperationType] = useState<'all' | 'insert' | 'update' | 'delete'>('all');
  const [operationDelay, setOperationDelay] = useState(1);
  const [batchSize, setBatchSize] = useState(1);

  useEffect(() => {
    loadData();
    // Set up polling for status updates
    const interval = setInterval(loadStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [connectionsData, tablesData] = await Promise.all([
        connectionApi.list(),
        tableApi.list(),
      ]);
      setConnections(connectionsData);
      setTableConfigs(tablesData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStatus = async () => {
    try {
      const response = await pillowFightApi.getStatus().catch(() => null);
      if (response && response.pillow_fights && response.pillow_fights.length > 0) {
        // Use the first pillow fight status for now
        const firstFight = response.pillow_fights[0];
        setPillowFightStatus({
          status: firstFight.status as 'idle' | 'running' | 'stopped' | 'error',
          message: firstFight.operations ? `Operations: ${Object.keys(firstFight.operations).length}` : undefined,
          connection_id: firstFight.connection_id,
          table_id: firstFight.table_id,
        });
      } else {
        setPillowFightStatus(null);
      }
    } catch (error) {
      console.error('Status update error:', error);
      setPillowFightStatus(null);
    }
  };

  const handleStartDialogOpen = () => {
    // Pre-select first connection and its tables
    if (connections.length > 0) {
      const connectionId = connections[0].id!;
      setSelectedConnection(connectionId);
      const connectionTables = tableConfigs
        .filter(config => config.connection_id === connectionId)
        .map(config => config.id!)
        .filter(id => id);
      setSelectedTables(connectionTables);
    }
    setStartDialogOpen(true);
  };

  const handleStartDialogClose = () => {
    setStartDialogOpen(false);
  };

  const handleTableToggle = (tableId: number) => {
    setSelectedTables(prev =>
      prev.includes(tableId)
        ? prev.filter(id => id !== tableId)
        : [...prev, tableId]
    );
  };

  const handleStartPillowFight = async () => {
    if (!selectedConnection || selectedTables.length === 0) {
      alert('Please select a connection and at least one table.');
      return;
    }

    try {
      const request: PillowFightRequest = {
        connection_id: selectedConnection,
        table_ids: selectedTables,
        operation_type: operationType,
        operation_delay: operationDelay,
        batch_size: batchSize,
      };

      const response = await pillowFightApi.start(request);

      // Check if the response indicates success or already running
      if (response.status === 'started' || response.status === 'already_running') {
        setStartDialogOpen(false);
        loadStatus(); // Refresh status immediately
      } else {
        throw new Error(`Unexpected status: ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to start pillow fight:', error);
      alert('Failed to start pillow fight. Please check your configuration.');
    }
  };

  const handleStopPillowFight = async () => {
    try {
      await pillowFightApi.stopAll();
      loadStatus(); // Refresh status immediately
    } catch (error) {
      console.error('Failed to stop pillow fight:', error);
      alert('Failed to stop pillow fight.');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'running':
        return 'success';
      case 'idle':
        return 'warning';
      case 'stopped':
        return 'error';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getAvailableTables = () => {
    if (!selectedConnection) return [];
    return (Array.isArray(tableConfigs) ? tableConfigs : []).filter(config => config.connection_id === selectedConnection);
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        Pillow Fight Control
      </Typography>

      <Grid container spacing={3}>
        {/* Status Card */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6">Current Status</Typography>
                <Button
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={loadStatus}
                  disabled={loading}
                >
                  Refresh
                </Button>
              </Box>

              {pillowFightStatus ? (
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Chip
                      label={pillowFightStatus?.status?.toUpperCase() }
                      color={getStatusColor(pillowFightStatus?.status || "unknown")}
                      size="small"
                    />
                    {pillowFightStatus.status === 'running' && (
                      <CircularProgress size={20} />
                    )}
                  </Box>

                  {pillowFightStatus.message && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {pillowFightStatus.message}
                    </Typography>
                  )}

                  {pillowFightStatus.connection_id && (
                    <Typography variant="body2" sx={{ mb: 1 }}>
                      <strong>Connection ID:</strong> {pillowFightStatus.connection_id}
                    </Typography>
                  )}

                  {pillowFightStatus.table_id && (
                    <Typography variant="body2" sx={{ mb: 2 }}>
                      <strong>Table ID:</strong> {pillowFightStatus.table_id}
                    </Typography>
                  )}
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No status information available
                </Typography>
              )}

              <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                <Button
                  variant="contained"
                  color="success"
                  startIcon={<PlayIcon />}
                  onClick={handleStartDialogOpen}
                  disabled={pillowFightStatus?.status === 'running' || connections.length === 0}
                  fullWidth
                >
                  Start Pillow Fight
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={handleStopPillowFight}
                  disabled={pillowFightStatus?.status !== 'running'}
                  fullWidth
                >
                  Stop
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Configuration Summary */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Configuration Summary
              </Typography>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Connections: {connections.length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Configured Tables: {tableConfigs.length}
                </Typography>
              </Box>

              {connections.length === 0 && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  No database connections configured. Please create a connection first.
                </Alert>
              )}

              {tableConfigs.length === 0 && connections.length > 0 && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  No tables configured for automation. Please configure tables first.
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Activity */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Activity
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Activity monitoring will be implemented here. This would show recent pillow fight operations,
                performance metrics, and system events.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Start Pillow Fight Dialog */}
      <Dialog
        open={startDialogOpen}
        onClose={handleStartDialogClose}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Start Pillow Fight</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <FormControl fullWidth>
              <InputLabel>Connection</InputLabel>
              <Select
                value={selectedConnection || ''}
                label="Connection"
                onChange={(e) => {
                  const connId = parseInt(e.target.value as string);
                  setSelectedConnection(connId);
                  const connectionTables = tableConfigs
                    .filter(config => config.connection_id === connId)
                    .map(config => config.id!)
                    .filter(id => id);
                  setSelectedTables(connectionTables);
                }}
              >
                {(Array.isArray(connections) ? connections : []).map((connection) => (
                  <MenuItem key={connection.id} value={connection.id}>
                    {connection.name} ({connection.db_type})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box>
              <Typography variant="h6" gutterBottom>
                Select Tables ({selectedTables.length} selected)
              </Typography>
              {getAvailableTables().length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No tables configured for the selected connection.
                </Typography>
              ) : (
                <List dense sx={{ maxHeight: 200, overflow: 'auto', border: 1, borderColor: 'divider', borderRadius: 1 }}>
                  {(Array.isArray(getAvailableTables()) ? getAvailableTables() : []).map((table) => (
                    <ListItem key={table.id} dense>
                      <Checkbox
                        checked={selectedTables.includes(table.id!)}
                        onChange={() => handleTableToggle(table.id!)}
                      />
                      <ListItemText
                        primary={`${table.table_name}`}
                        secondary={`${table.schema_name} • ${table.operation_type} • Delay: ${table.operation_delay}s`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>

            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>Operation Type</InputLabel>
                  <Select
                    value={operationType}
                    label="Operation Type"
                    onChange={(e) => setOperationType(e.target.value as typeof operationType)}
                  >
                    <MenuItem value="all">All Operations</MenuItem>
                    <MenuItem value="insert">Insert Only</MenuItem>
                    <MenuItem value="update">Update Only</MenuItem>
                    <MenuItem value="delete">Delete Only</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField
                  label="Delay (seconds)"
                  type="number"
                  value={operationDelay}
                  onChange={(e) => setOperationDelay(parseFloat(e.target.value) || 1)}
                  fullWidth
                  inputProps={{ min: 0.1, step: 0.1 }}
                />
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField
                  label="Batch Size"
                  type="number"
                  value={batchSize}
                  onChange={(e) => setBatchSize(parseInt(e.target.value) || 1)}
                  fullWidth
                  inputProps={{ min: 1 }}
                />
              </Grid>
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleStartDialogClose}>Cancel</Button>
          <Button
            onClick={handleStartPillowFight}
            variant="contained"
            color="success"
            disabled={!selectedConnection || selectedTables.length === 0}
          >
            Start Pillow Fight
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default PillowFight;
