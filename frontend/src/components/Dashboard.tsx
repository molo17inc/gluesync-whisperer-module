import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  Storage as StorageIcon,
  TableChart as TableIcon,
  PlayArrow as PlayIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { connectionApi, pillowFightApi, Connection, PillowFightStatus } from '../services/api';

const Dashboard: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [pillowFightStatus, setPillowFightStatus] = useState<PillowFightStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
    // Set up polling for status updates
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [connectionsData, statusData] = await Promise.all([
        connectionApi.list().catch(() => []),
        pillowFightApi.getStatus().catch(() => null),
      ]);
      setConnections(Array.isArray(connectionsData) ? connectionsData : []);
      setPillowFightStatus(statusData);
      setError(null);
    } catch (err) {
      setError('Failed to load dashboard data');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadStatus = async () => {
    try {
      const status = await pillowFightApi.getStatus().catch(() => null);
      setPillowFightStatus(status);
    } catch (err) {
      console.error('Status update error:', err);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'running':
        return 'success';
      case 'idle':
        return 'default';
      case 'stopped':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'running':
        return <CheckCircleIcon />;
      case 'idle':
        return <CheckCircleIcon />;
      case 'stopped':
        return <WarningIcon />;
      case 'error':
        return <ErrorIcon />;
      default:
        return <CheckCircleIcon />;
    }
  };

  if (loading) {
    return (
      <Box sx={{ width: '100%', mt: 2 }}>
        <LinearProgress />
      </Box>
    );
  }

  const safeConnections = Array.isArray(connections) ? connections : [];

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        Dashboard
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* System Status */}
        <Grid item xs={12} md={6} lg={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <PlayIcon sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">Pillow Fight Status</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {pillowFightStatus && getStatusIcon(pillowFightStatus.status)}
                <Chip
                  label={pillowFightStatus?.status || 'Unknown'}
                  color={getStatusColor(pillowFightStatus?.status || 'unknown')}
                  size="small"
                />
              </Box>
              {pillowFightStatus?.message && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {pillowFightStatus.message}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Connections Count */}
        <Grid item xs={12} md={6} lg={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <StorageIcon sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">Database Connections</Typography>
              </Box>
              <Typography variant="h3" color="primary.main">
                {safeConnections.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active connections
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Tables Configured */}
        <Grid item xs={12} md={6} lg={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TableIcon sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">Configured Tables</Typography>
              </Box>
              <Typography variant="h3" color="primary.main">
                0
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Tables ready for automation
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Connections */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Connections
              </Typography>
              {safeConnections.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No connections configured yet. Create your first connection to get started.
                </Typography>
              ) : (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {safeConnections.slice(0, 5).map((connection) => (
                    <Chip
                      key={connection?.id || Math.random()}
                      label={`${connection?.name || 'Unknown'} (${connection?.db_type || 'unknown'})`}
                      variant="outlined"
                      size="small"
                    />
                  ))}
                  {safeConnections.length > 5 && (
                    <Chip
                      label={`+${safeConnections.length - 5} more`}
                      variant="outlined"
                      size="small"
                      color="primary"
                    />
                  )}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
