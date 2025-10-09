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
  PlayArrow as PlayIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import { Connection, connectionApi } from '../services/api';

const Connections: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });
  const [formData, setFormData] = useState<Partial<Connection>>({
    name: '',
    description: '',
    db_type: 'mssql',
    host: '',
    port: 1433,
    username: '',
    password: '',
    database: '',
  });

  useEffect(() => {
    loadConnections();
  }, []);

  const loadConnections = async () => {
    console.log("Loading connections...");
    try {
      setLoading(true);
      const data = await connectionApi.list();
      setConnections(data);
    } catch (error) {
      showSnackbar('Failed to load connections', 'error');
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
      name: '',
      description: '',
      db_type: 'mssql',
      host: '',
      port: 1433,
      username: '',
      password: '',
      database: '',
    });
    setOpen(true);
  };

  const handleCloseDialog = () => {
    setOpen(false);
  };

  const handleInputChange = (field: keyof Connection, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    try {
      await connectionApi.create(formData as Connection);
      showSnackbar('Connection created successfully', 'success');
      handleCloseDialog();
      loadConnections();
    } catch (error) {
      const errorMessage = error?.response?.data?.detail || 'Failed to create connection';
      showSnackbar(errorMessage, 'error');
      showSnackbar('Failed to create connection', 'error');
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this connection?')) {
      try {
        await connectionApi.delete(id);
        showSnackbar('Connection deleted successfully', 'success');
        loadConnections();
      } catch (error) {
        showSnackbar('Failed to delete connection', 'error');
      }
    }
  };

  const handleStatusChange = async (id: number, currentStatus: string) => {
    const newStatus = currentStatus === 'running' ? 'idle' : 'running';
    try {
      await connectionApi.updateStatus(id, newStatus);
      showSnackbar(`Connection ${newStatus === 'running' ? 'started' : 'stopped'}`, 'success');
      loadConnections();
    } catch (error) {
      showSnackbar('Failed to update connection status', 'error');
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'running':
        return 'success';
      case 'idle':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Database Connections</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleOpenDialog}
        >
          New Connection
        </Button>
      </Box>

      <Card>
        <CardContent>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Host</TableCell>
                  <TableCell>Database</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(Array.isArray(connections) ? connections : []).map((connection) => (
                  <TableRow key={connection.id}>
                    <TableCell>
                      <Box>
                        <Typography variant="body1" fontWeight="medium">
                          {connection.name}
                        </Typography>
                        {connection.description && (
                          <Typography variant="body2" color="text.secondary">
                            {connection.description}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={connection.db_type.toUpperCase()}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      {connection.host}:{connection.port}
                    </TableCell>
                    <TableCell>
                      {connection.database || connection.database_name || 'N/A'}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={connection.status || 'unknown'}
                        size="small"
                        color={getStatusColor(connection.status)}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={() => handleStatusChange(connection.id!, connection.status || 'idle')}
                        color={connection.status === 'running' ? 'error' : 'success'}
                      >
                        {connection.status === 'running' ? <StopIcon /> : <PlayIcon />}
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(connection.id!)}
                        color="error"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
                {connections.length === 0 && !loading && (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                      <Typography variant="body2" color="text.secondary">
                        No connections found. Create your first connection to get started.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Create Connection Dialog */}
      <Dialog open={open} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>Create New Connection</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Name"
              value={formData.name}
              onChange={(e) => handleInputChange('name', e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Description"
              value={formData.description}
              onChange={(e) => handleInputChange('description', e.target.value)}
              fullWidth
              multiline
              rows={2}
            />
            <FormControl fullWidth>
              <InputLabel>Database Type</InputLabel>
              <Select
                value={formData.db_type}
                label="Database Type"
                onChange={(e) => handleInputChange('db_type', e.target.value as Connection['db_type'])}
              >
                <MenuItem value="mssql">MS SQL Server</MenuItem>
                <MenuItem value="as400">AS400</MenuItem>
                <MenuItem value="sqlite">SQLite</MenuItem>
              </Select>
            </FormControl>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                label="Host"
                value={formData.host}
                onChange={(e) => handleInputChange('host', e.target.value)}
                fullWidth
                required
              />
              <TextField
                label="Port"
                type="number"
                value={formData.port}
                onChange={(e) => handleInputChange('port', parseInt(e.target.value))}
                sx={{ width: 120 }}
                required
              />
            </Box>
            <TextField
              label="Username"
              value={formData.username}
              onChange={(e) => handleInputChange('username', e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Password"
              type="password"
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Database"
              required
              value={formData.database}
              onChange={(e) => handleInputChange('database', e.target.value)}
              fullWidth
              helperText="Database name (for MS SQL) or leave empty (for AS400)"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={!formData.name || !formData.host || !formData.username || !formData.password || !formData.database}
          >
            Create
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

export default Connections;
