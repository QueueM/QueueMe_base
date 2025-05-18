#!/bin/bash

# Check for required dependencies
command -v locust >/dev/null 2>&1 || { echo "Locust is required but not installed. Please run: pip install locust"; exit 1; }

# Default values
HOST=${1:-"https://api.queueme.net"}
USERS=${2:-50}
SPAWN_RATE=${3:-5}
RUNTIME=${4:-"3m"}
TEST_TYPE=${5:-"mixed"}

echo "=== QueueMe Load Testing Script ==="
echo "Host: $HOST"
echo "Number of users: $USERS"
echo "Spawn rate: $SPAWN_RATE"
echo "Runtime: $RUNTIME"
echo "Test type: $TEST_TYPE"
echo "==================================="

# Create results directory if it doesn't exist
RESULTS_DIR="load_tests/results"
mkdir -p $RESULTS_DIR

# Timestamp for this test run
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
CSV_PREFIX="${RESULTS_DIR}/${TIMESTAMP}_${TEST_TYPE}"

# Set up locust command with common arguments
LOCUST_CMD="locust --host=$HOST \
             --headless \
             --csv=$CSV_PREFIX \
             --users=$USERS \
             --spawn-rate=$SPAWN_RATE \
             --run-time=$RUNTIME \
             --logfile=${CSV_PREFIX}.log \
             -f load_tests/locustfile.py"

# Run the appropriate test based on test type
case $TEST_TYPE in
    "mixed")
        # Run test with mixed user types (default)
        $LOCUST_CMD QueueMeUser
        ;;
    "customers")
        # Run test with only customer users
        $LOCUST_CMD CustomerUser
        ;;
    "business")
        # Run test with only business users
        $LOCUST_CMD BusinessUser
        ;;
    "auth")
        # Run test focused on authentication
        $LOCUST_CMD QueueMeUser --tags auth
        ;;
    "bookings")
        # Run test focused on bookings
        $LOCUST_CMD QueueMeUser --tags customer
        ;;
    "search")
        # Run test focused on search
        $LOCUST_CMD QueueMeUser --tags common
        ;;
    *)
        # Unknown test type
        echo "Unknown test type: $TEST_TYPE"
        echo "Available test types: mixed, customers, business, auth, bookings, search"
        exit 1
        ;;
esac

# Generate HTML report
echo "Generating HTML report..."
python -c "
import pandas as pd
import matplotlib.pyplot as plt
import os

# Read the CSV files
stats = pd.read_csv('${CSV_PREFIX}_stats.csv')
failures = pd.read_csv('${CSV_PREFIX}_failures.csv')
history = pd.read_csv('${CSV_PREFIX}_stats_history.csv')

# Generate HTML report
html = f'''
<html>
<head>
    <title>Load Test Report - {stats['Name'].iloc[0]}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .summary {{ margin-bottom: 20px; }}
        .failures {{ margin-top: 20px; color: #e74c3c; }}
    </style>
</head>
<body>
    <h1>Load Test Report</h1>
    <div class='summary'>
        <h2>Summary</h2>
        <p>Total Requests: {stats['# requests'].sum()}</p>
        <p>Failed Requests: {stats['# failures'].sum()}</p>
        <p>Median Response Time: {stats['Median response time'].mean():.2f} ms</p>
        <p>95th Percentile: {stats['95%'].mean():.2f} ms</p>
        <p>Requests Per Second: {stats['Requests/s'].mean():.2f}</p>
        <p>Test Duration: {history['Timestamp'].max() - history['Timestamp'].min():.2f} seconds</p>
    </div>

    <h2>Request Statistics</h2>
    <table>
        <tr>
            <th>Name</th>
            <th>Count</th>
            <th>Failures</th>
            <th>Median (ms)</th>
            <th>Average (ms)</th>
            <th>95% (ms)</th>
            <th>Requests/s</th>
        </tr>
'''

for _, row in stats.iterrows():
    html += f'''
        <tr>
            <td>{row['Name']}</td>
            <td>{row['# requests']}</td>
            <td>{row['# failures']}</td>
            <td>{row['Median response time']:.2f}</td>
            <td>{row['Average response time']:.2f}</td>
            <td>{row['95%']:.2f}</td>
            <td>{row['Requests/s']:.2f}</td>
        </tr>
    '''

html += '''
    </table>
'''

if len(failures) > 0:
    html += '''
    <div class='failures'>
        <h2>Failures</h2>
        <table>
            <tr>
                <th>Request Type</th>
                <th>Error</th>
                <th>Occurrences</th>
            </tr>
    '''

    for _, row in failures.iterrows():
        html += f'''
            <tr>
                <td>{row['Method'] + ' ' + row['Name']}</td>
                <td>{row['Error']}</td>
                <td>{row['Occurrences']}</td>
            </tr>
        '''

    html += '''
        </table>
    </div>
    '''

html += '''
</body>
</html>
'''

with open('${CSV_PREFIX}_report.html', 'w') as f:
    f.write(html)
"

# Check if the test was successful
if [ $? -eq 0 ]; then
    echo "Load test completed successfully."
    echo "Results saved to ${CSV_PREFIX}_*.csv"
    echo "Report generated at ${CSV_PREFIX}_report.html"
else
    echo "Load test failed."
    exit 1
fi
