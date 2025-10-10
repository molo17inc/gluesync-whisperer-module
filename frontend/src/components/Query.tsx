import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Snackbar,
  Grid,
} from '@mui/material';
import {
  PlayArrow as ExecuteIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { Connection, QueryRequest, connectionApi, automationApi } from '../services/api';

interface QueryResult {
  columns?: string[];
  rows?: any[][];
  error?: string;
  execution_time?: number;
}

const Query: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  useEffect(() => {
    loadConnections();
  }, []);

  const loadConnections = async () => {
    try {
      const data = await connectionApi.list();
      setConnections(data);
      if (data.length > 0 && !selectedConnection) {
        setSelectedConnection(data[0].id!);
      }
    } catch (error) {
      showSnackbar('Failed to load connections', 'error');
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleExecuteQuery = async () => {
    if (!selectedConnection || !query.trim()) {
      showSnackbar('Please select a connection and enter a query', 'error');
      return;
    }

    setLoading(true);
    const startTime = Date.now();

    try {
      const request: QueryRequest = {
        connection_id: selectedConnection,
        query: query.trim(),
      };

      const response = await automationApi.executeQuery(request);
      const executionTime = Date.now() - startTime;

      // Transform the response to match frontend expectations
      const transformedResult: QueryResult = {
        execution_time: executionTime,
      };

      if (response.success) {
        // Convert results from list of dicts to list of arrays
        const rows: any[][] = [];
        if (response.results) {
          for (const rowDict of response.results) {
            const row: any[] = [];
            if (response.column_names) {
              for (const colName of response.column_names) {
                row.push(rowDict[colName]);
              }
            }
            rows.push(row);
          }
        }

        transformedResult.columns = response.column_names || [];
        transformedResult.rows = rows;
      } else {
        transformedResult.error = response.message;
      }

      setResult(transformedResult);

      showSnackbar('Query executed successfully', 'success');
    } catch (error: any) {
      setResult({
        error: error.response?.data?.detail || error.message || 'Query execution failed',
        execution_time: Date.now() - startTime,
      });
      showSnackbar('Query execution failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuery('');
    setResult(null);
  };

  const renderResultTable = () => {
    if (!result || !result.columns || !result.rows) return null;

    return (
      <TableContainer component={Paper} sx={{ mt: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {(result?.columns && Array.isArray(result.columns) ? result.columns : []).map((column, index) => (
                <TableCell key={index} sx={{ fontWeight: 'bold', bgcolor: 'grey.100' }}>
                  {column}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {(result?.rows && Array.isArray(result.rows) ? result.rows : []).map((row, rowIndex) => (
              <TableRow key={rowIndex} hover>
                {(Array.isArray(row) ? row : []).map((cell, cellIndex) => (
                  <TableCell key={cellIndex}>
                    {cell === null ? <em>null</em> : String(cell)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  const sampleQueries = [
    { label: 'Count records in DRIVERS table', query: 'SELECT COUNT(*) FROM DRIVERS' },
    { label: 'Show first 10 records', query: 'SELECT * FROM DRIVERS LIMIT 10' },
    { label: 'Show table structure', query: 'DESCRIBE DRIVERS' },
    { label: 'Show available tables', query: 'SHOW TABLES' },
  ];

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        SQL Query Executor
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Sample Queries
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Click on a sample query to use it:
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {(Array.isArray(sampleQueries) ? sampleQueries : []).map((sample, index) => (
                  <Button
                    key={index}
                    variant="outlined"
                    size="small"
                    onClick={() => setQuery(sample.query)}
                    sx={{ justifyContent: 'flex-start', textAlign: 'left', fontSize: '0.75rem' }}
                  >
                    {sample.label}
                  </Button>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box sx={{ mb: 2 }}>
                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Database Connection</InputLabel>
                  <Select
                    value={selectedConnection || ''}
                    label="Database Connection"
                    onChange={(e) => setSelectedConnection(parseInt(e.target.value as string))}
                  >
                    {(Array.isArray(connections) ? connections : []).map((connection) => (
                      <MenuItem key={connection.id} value={connection.id}>
                        {connection.name} ({connection.db_type})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <TextField
                  label="SQL Query"
                  multiline
                  rows={8}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  fullWidth
                  placeholder="Enter your SQL query here..."
                  sx={{ mb: 2 }}
                />

                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    variant="contained"
                    startIcon={loading ? <CircularProgress size={20} /> : <ExecuteIcon />}
                    onClick={handleExecuteQuery}
                    disabled={loading || !selectedConnection || !query.trim()}
                    fullWidth
                  >
                    {loading ? 'Executing...' : 'Execute Query'}
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<ClearIcon />}
                    onClick={handleClear}
                    fullWidth
                  >
                    Clear
                  </Button>
                </Box>
              </Box>

              {result && (
                <Box>
                  <Typography variant="h6" gutterBottom>
                    Query Results
                  </Typography>

                  {result.execution_time && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Execution time: {result.execution_time}ms
                    </Typography>
                  )}

                  {result.error ? (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {result.error}
                    </Alert>
                  ) : result.rows && result.rows.length === 0 ? (
                    <Alert severity="info" sx={{ mb: 2 }}>
                      Query executed successfully. No results returned.
                    </Alert>
                  ) : (
                    <>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {result.rows?.length || 0} rows returned
                      </Typography>
                      {renderResultTable()}
                    </>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

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

export default Query;
