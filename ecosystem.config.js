/**
 * PM2 Ecosystem Configuration for VWAP Prediction System
 *
 * Usage:
 *   pm2 start ecosystem.config.js          # Start all apps
 *   pm2 start ecosystem.config.js --only vwap-frontend  # Start only frontend
 *   pm2 logs vwap-frontend                 # View logs
 *   pm2 stop vwap-frontend                 # Stop frontend
 *   pm2 restart vwap-frontend              # Restart frontend
 *   pm2 delete vwap-frontend               # Remove from pm2
 *   pm2 monit                              # Monitor all processes
 */

module.exports = {
  apps: [
    {
      name: 'vwap-frontend',
      script: '/Users/m2/anaconda3/envs/quantum/bin/python',
      args: 'vwap_prediction_frontend.py',
      cwd: '/Users/m2/PycharmProjects/vwap_prediction',

      // Interpreter
      interpreter: 'none',  // We're calling python directly

      // Instances
      instances: 1,
      exec_mode: 'fork',

      // Restart behavior
      autorestart: true,
      watch: false,  // Set to true to auto-restart on file changes
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 8000,  // Increased to avoid port conflicts

      // Logging
      error_file: '/Users/m2/PycharmProjects/vwap_prediction/logs/vwap-frontend-error.log',
      out_file: '/Users/m2/PycharmProjects/vwap_prediction/logs/vwap-frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,

      // Environment variables
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/Users/m2/quantum-trading-system/python'
      },

      // Resource limits (optional)
      max_memory_restart: '1G',

      // Kill timeout
      kill_timeout: 10000,  // Increased to allow port release

      // Process control
      listen_timeout: 10000,
      shutdown_with_message: true,
    }
  ]
};
