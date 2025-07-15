# Social Trend Agent

An AI-powered social trend analysis and Twitter automation system that monitors Reddit for viral content, analyzes trends, and automatically generates and posts engaging tweets.

## 🚀 Features

- **Intelligent Content Discovery**: Scrapes Reddit posts using PRAW and Stagehand-py
- **Virality Scoring**: Advanced algorithm to predict viral potential based on upvote velocity, engagement, and recency
- **AI Content Generation**: Uses GPT-4o to create engaging tweets from Reddit posts
- **Automated Posting**: Posts to Twitter using Tweepy with rate limiting and error handling
- **Metrics Collection**: Tracks engagement metrics (likes, retweets, replies) after posting
- **Workflow Orchestration**: LangGraph-based state machine for reliable execution
- **REST API**: FastAPI backend with comprehensive endpoints
- **Scheduling**: Automated execution with APScheduler
- **Monitoring**: Health checks, performance metrics, and Prometheus integration
- **Docker Deployment**: Complete containerization with docker-compose
- **Comprehensive Testing**: Unit and integration tests with pytest

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Reddit API    │    │   OpenAI API    │    │  Twitter API    │
│     (PRAW)      │    │    (GPT-4o)     │    │   (Tweepy)      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ Scrape  │─▶│  Score  │─▶│Generate │─▶│  Post   │           │
│  │ Sources │  │Virality │  │Content  │  │Content  │           │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
└─────────────────────────────────────────────────────────────────┘
          │                                              │
          ▼                                              ▼
┌─────────────────┐                            ┌─────────────────┐
│   SQLite DB     │                            │  Metrics API    │
│  (Tortoise ORM) │                            │  (Collection)   │
└─────────────────┘                            └─────────────────┘
          │                                              │
          ▼                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Scheduler   │  │ Monitoring  │  │ REST API    │            │
│  │(APScheduler)│  │ (Health)    │  │ Endpoints   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- API Keys:
  - Reddit API (client_id, client_secret)
  - Twitter API v2 (bearer_token, api_key, api_secret, access_token, access_token_secret)
  - OpenAI API (api_key)
  - Stagehand/Browserbase API (optional, for enhanced scraping)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd social_trend_agent

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### 2. Configure Environment Variables

Edit `.env` file with your API credentials:

```env
# Reddit API Configuration
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=TrendBot/1.0

# Twitter API Configuration
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
GPT_MODEL=gpt-4o

# Application Configuration
MIN_SCORE=200
SUBREDDITS=interestingasfuck,technology,pics
INTERVAL_MINUTES=5
```

### 3. Deploy with Docker

```bash
# Make deployment script executable
chmod +x docker/deploy.sh

# Deploy the application
./docker/deploy.sh
```

### 4. Access the Application

- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## 🛠️ Development Setup

### Local Development

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run tests
python run_tests.py

# Start development server
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

### Development with Docker

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

## 📚 API Documentation

### Core Endpoints

#### Start Workflow
```http
POST /workflow/run
Content-Type: application/json

{
  "min_score": 200,
  "subreddits": ["technology", "programming"]
}
```

#### Get Workflow Status
```http
GET /workflow/status/{workflow_id}
```

#### Get Recent Workflows
```http
GET /workflow/recent
```

#### Health Check
```http
GET /health
```

#### Collect Metrics
```http
POST /metrics/collect
```

#### Get Metrics Summary
```http
GET /metrics/summary
```

### Scheduler Endpoints

#### Get Scheduler Status
```http
GET /scheduler/status
```

#### Start/Stop Scheduler
```http
POST /scheduler/start
POST /scheduler/stop
```

### Statistics Endpoints

#### 24-Hour Statistics
```http
GET /stats/24h
```

#### Recent Posts
```http
GET /posts/recent
```

#### Successful Posts
```http
GET /posts/successful
```

## 🔧 Configuration

### Application Settings

The application can be configured through environment variables or the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `MIN_SCORE` | Minimum virality score threshold | 200 |
| `SUBREDDITS` | Comma-separated list of subreddits | interestingasfuck,technology,pics |
| `INTERVAL_MINUTES` | Workflow execution interval | 5 |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8000 |
| `DEBUG` | Debug mode | false |
| `LOG_LEVEL` | Logging level | INFO |
| `LOG_FORMAT` | Log format (text/json) | json |

### Virality Scoring

The virality scoring algorithm considers:

- **Upvote Velocity**: Upvotes per hour since posting
- **Comment Ratio**: Comments to upvotes ratio
- **Recency Factor**: Time-based decay factor
- **Engagement Score**: Weighted combination of factors

Formula:
```
score = (upvote_velocity * 0.4) + (comment_ratio * 100 * 0.3) + (recency_factor * 100 * 0.3)
```

### Content Generation

GPT-4o generates tweets using:
- Post title and content
- Subreddit context
- Trending hashtags
- Character limit optimization
- Engagement-focused prompts

## 🧪 Testing

### Run All Tests
```bash
python run_tests.py full
```

### Run Specific Test Types
```bash
# Unit tests only
python run_tests.py unit

# Integration tests only
python run_tests.py integration

# Performance tests
python run_tests.py performance

# Coverage report
python run_tests.py coverage

# Code quality checks
python run_tests.py lint
python run_tests.py type
python run_tests.py security
```

### Test Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── unit/                    # Unit tests
│   ├── test_state.py       # State management tests
│   └── test_scoring.py     # Scoring algorithm tests
└── integration/             # Integration tests
    └── test_workflow.py     # End-to-end workflow tests
```

## 📊 Monitoring

### Health Monitoring

The application includes comprehensive health monitoring:

- **System Metrics**: CPU, memory, disk usage
- **Application Health**: Database, scheduler, API status
- **Performance Metrics**: Response times, throughput
- **Error Tracking**: Error rates, failure patterns

### Prometheus Metrics

Available at `/metrics` endpoint:

- `workflow_executions_total`
- `posts_scraped_total`
- `posts_posted_total`
- `api_requests_total`
- `system_cpu_percent`
- `system_memory_percent`

### Grafana Dashboards

Pre-configured dashboards for:
- System overview
- Workflow performance
- API metrics
- Error tracking

## 🐳 Docker Deployment

### Production Deployment

```bash
# Deploy with monitoring
docker-compose up -d

# View logs
docker-compose logs -f trend-agent

# Scale services
docker-compose up -d --scale trend-agent=2
```

### Development Deployment

```bash
# Development with hot reload
docker-compose -f docker-compose.dev.yml up -d
```

### Update Deployment

```bash
# Update to latest version
./docker/update.sh
```

## 🔒 Security

### API Security

- Rate limiting on all endpoints
- Input validation with Pydantic
- Error handling without information leakage
- CORS configuration for web access

### Secrets Management

- Environment variables for sensitive data
- No hardcoded credentials
- Docker secrets support
- .env file exclusion from version control

### Security Scanning

```bash
# Run security checks
python run_tests.py security

# Manual security scan
bandit -r trend_graph/ backend/
```

## 📈 Performance

### Optimization Features

- Async/await throughout the application
- Connection pooling for APIs
- Database query optimization
- Caching for frequently accessed data
- Rate limiting to respect API limits

### Performance Monitoring

- Request/response timing
- Database query performance
- Memory usage tracking
- CPU utilization monitoring

### Scaling Considerations

- Horizontal scaling with multiple containers
- Database connection pooling
- Redis for distributed caching (future enhancement)
- Load balancing support

## 🚨 Troubleshooting

### Common Issues

#### API Rate Limits
```bash
# Check rate limit status
curl http://localhost:8000/stats/24h

# Adjust interval in .env
INTERVAL_MINUTES=10
```

#### Database Issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d
```

#### Memory Issues
```bash
# Check memory usage
curl http://localhost:8000/health

# Restart services
docker-compose restart
```

### Logs

```bash
# View application logs
docker-compose logs -f trend-agent

# View specific service logs
docker-compose logs -f prometheus
docker-compose logs -f grafana
```

### Debug Mode

```bash
# Enable debug mode
echo "DEBUG=true" >> .env
docker-compose restart trend-agent
```

## 🤝 Contributing

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run the full test suite
5. Submit a pull request

### Code Quality

```bash
# Format code
black trend_graph/ backend/ tests/
isort trend_graph/ backend/ tests/

# Lint code
flake8 trend_graph/ backend/ tests/

# Type checking
mypy trend_graph/ backend/

# Security scan
bandit -r trend_graph/ backend/
```

### Testing Requirements

- All new features must include tests
- Maintain >80% code coverage
- Integration tests for workflow changes
- Performance tests for critical paths

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **LangGraph**: Workflow orchestration framework
- **FastAPI**: Modern web framework for APIs
- **PRAW**: Python Reddit API Wrapper
- **Tweepy**: Twitter API library
- **OpenAI**: GPT-4o language model
- **Stagehand**: Browser automation platform

## 📞 Support

For support and questions:

1. Check the troubleshooting section
2. Review the API documentation
3. Check existing issues
4. Create a new issue with detailed information

## 🗺️ Roadmap

### Upcoming Features

- [ ] Multi-platform support (LinkedIn, Facebook)
- [ ] Advanced analytics dashboard
- [ ] Machine learning for better scoring
- [ ] Real-time trend detection
- [ ] A/B testing for content generation
- [ ] Advanced scheduling options
- [ ] Webhook integrations
- [ ] Custom scoring algorithms

### Performance Improvements

- [ ] Redis caching layer
- [ ] Database sharding
- [ ] CDN integration
- [ ] Advanced monitoring
- [ ] Auto-scaling capabilities

---

**Built with ❤️ for social media automation and trend analysis**

