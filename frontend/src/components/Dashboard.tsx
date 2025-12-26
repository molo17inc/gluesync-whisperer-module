import React, { useState, useEffect } from "react";
import Grid from "@mui/material/Grid";
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  LinearProgress,
  Alert,
} from "@mui/material";
import {
  Storage as StorageIcon,
  TableChart as TableIcon,
  PlayArrow as PlayIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
} from "@mui/icons-material";
import {
  connectionApi,
  pillowFightApi,
  tableApi,
  Connection,
  PillowFightJobStatus,
} from "../services/api";

const Dashboard: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [jobSummary, setJobSummary] = useState<{
    status: string;
    message?: string;
    activeJobs: number;
    runningTables: number;
  } | null>(null);
  const [tableCount, setTableCount] = useState<number>(0);
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
      const [connectionsData, jobsResponse, tablesData] = await Promise.all([
        connectionApi.list().catch(() => []),
        pillowFightApi.listJobs().catch(() => ({ jobs: [] })),
        tableApi.list().catch(() => []),
      ]);
      setConnections(Array.isArray(connectionsData) ? connectionsData : []);
      const jobs = Array.isArray(jobsResponse?.jobs) ? jobsResponse.jobs : [];
      setJobSummary(deriveJobSummary(jobs));
      setTableCount(Array.isArray(tablesData) ? tablesData.length : 0);
      setError(null);
    } catch (err) {
      setError("Failed to load dashboard data");
      console.error("Dashboard error:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadStatus = async () => {
    try {
      const response = await pillowFightApi
        .listJobs()
        .catch(() => ({ jobs: [] }));
      const jobs = Array.isArray(response?.jobs) ? response.jobs : [];
      setJobSummary(deriveJobSummary(jobs));
    } catch (err) {
      console.error("Status update error:", err);
    }
  };

  const deriveJobSummary = (jobs: PillowFightJobStatus[]) => {
    if (!jobs.length) {
      return {
        status: "idle",
        message: "No pillow fight jobs have been started yet.",
        activeJobs: 0,
        runningTables: 0,
      };
    }

    const normalizedStatuses = jobs.map(
      (job) => job.status?.toLowerCase() ?? "unknown"
    );
    const activeJobs = jobs.filter((job) =>
      ["pending", "running"].includes(job.status?.toLowerCase() ?? "")
    ).length;
    const runningTables = jobs.reduce(
      (sum, job) =>
        sum +
        job.tables.filter((table) =>
          ["pending", "running"].includes(table.status?.toLowerCase() ?? "")
        ).length,
      0
    );

    let status = "completed";
    let message = "All pillow fight jobs are completed.";

    if (normalizedStatuses.includes("error")) {
      status = "error";
      message = "One or more jobs encountered errors.";
    } else if (normalizedStatuses.includes("running")) {
      status = "running";
      message = "Jobs are currently running.";
    } else if (normalizedStatuses.includes("pending")) {
      status = "pending";
      message = "Jobs are pending execution.";
    }

    return {
      status,
      message,
      activeJobs,
      runningTables,
    };
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case "running":
        return "success";
      case "idle":
        return "default";
      case "stopped":
        return "warning";
      case "error":
        return "error";
      default:
        return "default";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case "running":
        return <CheckCircleIcon />;
      case "idle":
        return <CheckCircleIcon />;
      case "stopped":
        return <WarningIcon />;
      case "error":
        return <ErrorIcon />;
      default:
        return <CheckCircleIcon />;
    }
  };

  if (loading) {
    return (
      <Box sx={{ width: "100%", mt: 2 }}>
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
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <PlayIcon sx={{ mr: 1, color: "primary.main" }} />
                <Typography variant="h6">Pillow fight Status</Typography>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                {jobSummary && getStatusIcon(jobSummary.status)}
                <Chip
                  label={
                    jobSummary?.status
                      ? jobSummary.status.toUpperCase()
                      : "UNKNOWN"
                  }
                  color={getStatusColor(jobSummary?.status || "unknown")}
                  size="small"
                />
              </Box>
              {jobSummary?.message && (
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 1 }}
                >
                  {jobSummary.message}
                </Typography>
              )}
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Active jobs: {jobSummary?.activeJobs ?? 0} • Active tables:{" "}
                {jobSummary?.runningTables ?? 0}
              </Typography>
              {jobSummary?.status === "idle" && (
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 1 }}
                >
                  Start a pillow fight job from the Pillow fight console.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Connections Count */}
        <Grid item xs={12} md={6} lg={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <StorageIcon sx={{ mr: 1, color: "primary.main" }} />
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
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <TableIcon sx={{ mr: 1, color: "primary.main" }} />
                <Typography variant="h6">Configured Tables</Typography>
              </Box>
              <Typography variant="h3" color="primary.main">
                {tableCount}
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
                  No connections configured yet. Create your first connection to
                  get started.
                </Typography>
              ) : (
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                  {safeConnections.slice(0, 5).map((connection) => (
                    <Chip
                      key={connection?.id || Math.random()}
                      label={`${connection?.name || "Unknown"} (${
                        connection?.db_type || "unknown"
                      })`}
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
