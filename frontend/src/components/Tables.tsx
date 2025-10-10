import React, { useState, useEffect } from 'react';
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
  InputLabel,
  Select,
  MenuItem,
  Chip,
  IconButton,
  Alert,
  Snackbar,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  TableChart as TableIcon,
} from '@mui/icons-material';
import {
  Connection,
  TableConfig,
  Schema,
  Table as DBTable,
  connectionApi,
  tableApi,
} from '../services/api';

const Tables: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tableConfigs, setTableConfigs] = useState<TableConfig[]>([]);
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [tables, setTables] = useState<DBTable[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [loadingSchemas, setLoadingSchemas] = useState(false);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });
  const [formData, setFormData] = useState<Partial<TableConfig>>({
    table_name: '',
    schema_name: '',
    operation_type: 'all',
    operation_delay: 1,
    batch_size: 1,
    enabled: true,
    connection_id: 0,
  });
  const [selectedConnection, setSelectedConnection] = useState<Connection | null>(null);

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
      console.log('✅ Initial data loaded:', {
        connectionsCount: connectionsData?.length || 0,
        tableConfigsCount: tablesData?.length || 0
      });
      setConnections(connectionsData);
      setTableConfigs(tablesData);
    } catch (error) {
      console.error('Failed to load initial data:', error);
      showSnackbar('Failed to load data', 'error');
    } finally {
      setLoading(false);
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleOpenDialog = () => {
    setFormData({
      table_name: '',
      schema_name: '',
      operation_type: 'all',
      operation_delay: 1,
      batch_size: 1,
      enabled: true,
      connection_id: 0,
    });
    setSelectedConnection(null);
    setSchemas([]);
    setTables([]);
    setOpen(true);
  };

  const handleCloseDialog = () => {
    setOpen(false);
  };

  const handleConnectionChange = async (connectionId: number) => {
    const connection = (Array.isArray(connections) ? connections : []).find(c => c.id === connectionId);
    if (!connection) return;

    setSelectedConnection(connection);
    setFormData(prev => ({ ...prev, connection_id: connectionId }));

    console.log('🔄 Starting to load schemas for connection:', connectionId);
    setLoadingSchemas(true);
    try {
      const schemasData = await connectionApi.getSchemas(connectionId);
      console.log('✅ Schemas loaded successfully:', schemasData?.length || 0, 'schemas found');
      // Convert string array to Schema objects for frontend compatibility
      const schemaObjects = schemasData.map((schema: string) => ({ name: schema }));
      setSchemas(schemaObjects);
    } catch (error) {
      console.error('Failed to load schemas:', error);
      showSnackbar('Failed to load schemas', 'error');
    } finally {
      setLoadingSchemas(false);
    }
  };

  const handleSchemaChange = async (schemaName: string) => {
    if (!selectedConnection) return;

    setFormData(prev => ({ ...prev, schema_name: schemaName }));

    try {
      const tablesData = await connectionApi.getTables(selectedConnection.id!, schemaName);
      setTables(tablesData);
    } catch (error) {
      console.error('Failed to load tables:', error);
      showSnackbar('Failed to load tables', 'error');
    }
  };

  const handleInputChange = (field: keyof TableConfig, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    if (!formData.table_name || !formData.schema_name || !formData.connection_id) {
      showSnackbar('Please fill in all required fields', 'error');
      return;
    }

    try {
      await tableApi.create(formData as TableConfig);
      showSnackbar('Table configuration created successfully', 'success');
      handleCloseDialog();
      loadData();
    } catch (error) {
      showSnackbar('Failed to create table configuration', 'error');
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this table configuration?')) {
      try {
        await tableApi.delete(id);
        showSnackbar('Table configuration deleted successfully', 'success');
        loadData();
      } catch (error) {
        showSnackbar('Failed to delete table configuration', 'error');
      }
    }
  };

  const getConnectionName = (connectionId: number) => {
    const connection = (Array.isArray(connections) ? connections : []).find(c => c.id === connectionId);
    return connection ? connection.name : 'Unknown';
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Table Configurations</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleOpenDialog}
          disabled={connections.length === 0}
        >
          Configure Table
        </Button>
      </Box>

      {connections.length === 0 && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          No database connections available. Please create a connection first before configuring tables.
        </Alert>
      )}

      <Card>
        <CardContent>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Table Name</TableCell>
                  <TableCell>Schema</TableCell>
                  <TableCell>Connection</TableCell>
                  <TableCell>Operation Type</TableCell>
                  <TableCell>Settings</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(Array.isArray(tableConfigs) ? tableConfigs : []).map((config) => (
                  <TableRow key={config.id}>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <TableIcon sx={{ mr: 1, color: 'primary.main' }} />
                        <Typography variant="body1" fontWeight="medium">
                          {config.table_name}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>{config.schema_name}</TableCell>
                    <TableCell>{getConnectionName(config.connection_id)}</TableCell>
                    <TableCell>
                      <Chip
                        label={config.operation_type.toUpperCase()}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    </TableCell>
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
                        label={config.enabled ? 'Enabled' : 'Disabled'}
                        size="small"
                        color={config.enabled ? 'success' : 'warning'}
                      />
                    </TableCell>
                    <TableCell align="right">
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
                {tableConfigs.length === 0 && !loading && (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                      <Typography variant="body2" color="text.secondary">
                        No table configurations found. Configure your first table to get started with automation.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Configure Table Dialog */}
      <Dialog open={open} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>Configure Table for Automation</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Connection</InputLabel>
              <Select
                value={formData.connection_id || ''}
                label="Connection"
                onChange={(e) => {
                  const value = e.target.value;
                  handleConnectionChange(typeof value === 'string' ? parseInt(value, 10) : value);
                }}
              >
                {(Array.isArray(connections) ? connections : []).map((connection) => (
                  <MenuItem key={`connection-${connection.id || connection.name}`} value={connection.id?.toString() || ''}>
                    {connection.name} ({connection.db_type})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {schemas.length > 0 && (
              <FormControl fullWidth>
                <InputLabel>Schema</InputLabel>
                <Select
                  value={formData.schema_name}
                  label="Schema"
                  onChange={(e) => handleSchemaChange(e.target.value)}
                >
                  {(Array.isArray(schemas) ? schemas : []).map((schema, index) => (
                    <MenuItem key={`schema-${typeof schema === 'string' ? schema : schema.name || `unnamed-${index}`}`} value={typeof schema === 'string' ? schema : schema.name}>
                      {typeof schema === 'string' ? schema : schema.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {tables.length > 0 && (
              <FormControl fullWidth>
                <InputLabel>Table</InputLabel>
                <Select
                  value={formData.table_name}
                  label="Table"
                  onChange={(e) => handleInputChange('table_name', e.target.value)}
                >
                  {(Array.isArray(tables) ? tables : []).map((table, index) => (
                    <MenuItem key={`table-${table.name || `unnamed-${index}`}`} value={table.name}>
                      {table.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            <Box sx={{ display: 'flex', gap: 2 }}>
              <Box sx={{ flex: '1 1 50%' }}>
                <FormControl fullWidth>
                  <InputLabel>Operation Type</InputLabel>
                  <Select
                    value={formData.operation_type}
                    label="Operation Type"
                    onChange={(e) => handleInputChange('operation_type', e.target.value as TableConfig['operation_type'])}
                  >
                    <MenuItem value="all">All Operations</MenuItem>
                    <MenuItem value="insert">Insert Only</MenuItem>
                    <MenuItem value="update">Update Only</MenuItem>
                    <MenuItem value="delete">Delete Only</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box sx={{ flex: '1 1 25%' }}>
                <TextField
                  label="Delay (seconds)"
                  type="number"
                  value={formData.operation_delay}
                  onChange={(e) => handleInputChange('operation_delay', parseFloat(e.target.value) || 1)}
                  fullWidth
                  inputProps={{ min: 0.1, step: 0.1 }}
                />
              </Box>
              <Box sx={{ flex: '1 1 25%' }}>
                <TextField
                  label="Batch Size"
                  type="number"
                  value={formData.batch_size}
                  onChange={(e) => handleInputChange('batch_size', parseInt(e.target.value) || 1)}
                  fullWidth
                  inputProps={{ min: 1 }}
                />
              </Box>
            </Box>

            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={formData.enabled ? 'enabled' : 'disabled'}
                label="Status"
                onChange={(e) => handleInputChange('enabled', e.target.value === 'enabled')}
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
            disabled={!formData.table_name || !formData.schema_name || !formData.connection_id}
          >
            Configure Table
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Tables;
