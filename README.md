# Stealth Monitor Analytics Dashboard

A comprehensive real-time productivity analytics dashboard for the Stealth Monitor system.

## Features

- Multi-page dashboard with navigation
- Overview: Key metrics, KPIs, and summary stats
- User Analysis: Individual user productivity tracking
- Session Details: Detailed session breakdown
- Trends: Time-series analysis and patterns
- Heatmaps: Activity distribution visualization
- App/URL Analysis: Application and website usage breakdown
- Interactive charts with Plotly
- Real-time auto-refresh (30 seconds)

## Requirements

- Python 3.8 or higher
- MongoDB connection (MongoDB Atlas or local instance)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure MongoDB connection:
   - Open `app.py`
   - Update the MongoDB connection string on line 51:
     ```python
     client = MongoClient("your-mongodb-connection-string")
     ```

## Running Locally

```bash
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

## Deployment

### Deploy to Streamlit Cloud

1. Push this folder to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub account
4. Select your repository and the `deployment` folder
5. Set the main file as `app.py`
6. Add secrets in Streamlit Cloud dashboard:
   - Go to App Settings > Secrets
   - Add your MongoDB connection string:
     ```toml
     [mongodb]
     connection_string = "mongodb+srv://username:password@cluster.mongodb.net/"
     ```
7. Update `app.py` to use secrets:
   ```python
   import streamlit as st
   client = MongoClient(st.secrets["mongodb"]["connection_string"])
   ```

### Deploy to Heroku

1. Create a `Procfile`:
```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

2. Create `setup.sh`:
```bash
mkdir -p ~/.streamlit/
echo "[server]
headless = true
port = $PORT
enableCORS = false
" > ~/.streamlit/config.toml
```

3. Deploy:
```bash
heroku login
heroku create your-app-name
git push heroku main
```

### Deploy to AWS/Azure/GCP

Use Docker container:

1. Create `Dockerfile` (see below)
2. Build: `docker build -t stealth-dashboard .`
3. Run: `docker run -p 8501:8501 stealth-dashboard`
4. Deploy to your cloud platform

## Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t stealth-dashboard .
docker run -p 8501:8501 stealth-dashboard
```

## Configuration

### Environment Variables

- `MONGODB_URI`: MongoDB connection string
- `PORT`: Server port (default: 8501)

### Customization

- **Theme**: Edit `.streamlit/config.toml`
- **Refresh interval**: Modify line 43 in `app.py`:
  ```python
  st_autorefresh(interval=30 * 1000, key="dashboard_refresh")
  ```
- **Auto-refresh rate**: Change `30` to desired seconds

## Database Structure

The dashboard expects the following MongoDB structure:

```javascript
// Database: stealth_monitor
// Collection: users
{
  username: "user1",
  dates: [
    {
      date: "2025-12-02",
      sessions: [
        {
          session_id: "abc123",
          start_time: "09:00:00",
          end_time: "17:00:00",
          productive_time: 1200,
          neutral_time: 800,
          wasted_time: 400,
          idle_time: 600,
          total_time: 3000,
          session_shift: "onshift",
          usage_breakdown: {
            productive: { "app1": { total_time: 600, visits: [] } },
            wasted: { "app2": { total_time: 400, visits: [] } }
          }
        }
      ]
    }
  ]
}
```

## Troubleshooting

### MongoDB Connection Issues
- Check connection string format
- Verify IP whitelist in MongoDB Atlas
- Check firewall settings

### Performance Issues
- Increase cache TTL in `@st.cache_data(ttl=30)`
- Reduce auto-refresh interval
- Add database indexes on frequently queried fields

### Memory Issues
- Limit date ranges in queries
- Reduce the number of sessions displayed
- Implement pagination for large datasets

## Support

For issues and questions, contact the development team.

## License

Proprietary - Stealth Monitor System
