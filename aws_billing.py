import boto3
import argparse
import datetime
import csv
import json
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

def get_billing_data(start_date, end_date, metrics):
    try:
        client = boto3.client('ce')
    except (NoCredentialsError, PartialCredentialsError):
        print("AWS credentials not found. Please configure your AWS credentials.")
        return None

    try:
        response = client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='MONTHLY',
            Metrics=metrics,
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                },
            ]
        )
    except client.exceptions.DataUnavailableException:
        print("Cost and usage data is not yet available for the specified period.")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

    return response

def aggregate_billing_data(response, metrics):
    if not response:
        return []

    aggregated_data = {}
    results = response.get('ResultsByTime', [])

    for result in results:
        groups = result.get('Groups', [])
        if not groups:
            continue

        for group in groups:
            service = group['Keys'][0]
            if service not in aggregated_data:
                aggregated_data[service] = {metric: 0.0 for metric in metrics}
                aggregated_data[service]['Unit'] = group['Metrics'][metrics[0]]['Unit']

            for metric in metrics:
                amount = float(group['Metrics'][metric]['Amount'])
                aggregated_data[service][metric] += amount

    return aggregated_data

def print_billing_data(aggregated_data, metrics, start_date, end_date, output_file=None, output_format=None):
    data = []
    total_costs = {metric: 0.0 for metric in metrics}

    for service, metrics_data in aggregated_data.items():
        record = {
            'Service': service,
            'Unit': metrics_data['Unit']
        }
        for metric in metrics:
            amount = metrics_data[metric]
            record[metric] = amount
            total_costs[metric] += amount
        data.append(record)

    if output_file:
        if output_format.lower() == 'csv':
            write_csv(data, metrics, output_file)
        elif output_format.lower() == 'json':
            write_json(data, metrics, start_date, end_date, output_file)
        else:
            print(f"Unsupported output format: {output_format}")
            return
        print(f"Billing data has been written to {output_file}")
    else:
        print(f"\nBilling Period: {start_date} to {end_date}")
        for record in data:
            print(f"  Service: {record['Service']}")
            for metric in metrics:
                amount = record[metric]
                unit = record['Unit']
                print(f"    {metric}: {amount:.2f} {unit}")
        print("\nTotal Costs:")
        for metric in metrics:
            unit = data[0]['Unit'] if data else 'USD'
            print(f"  {metric}: {total_costs[metric]:.2f} {unit}")

def write_csv(data, metrics, output_file):
    fieldnames = ['Service'] + metrics + ['Unit']

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for record in data:
            writer.writerow(record)

def write_json(data, metrics, start_date, end_date, output_file):
    output_data = {
        'BillingPeriod': {
            'Start': start_date,
            'End': end_date
        },
        'Services': data
    }
    with open(output_file, 'w') as jsonfile:
        json.dump(output_data, jsonfile, indent=4)

def parse_date(date_str):
    try:
        return datetime.datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f"Not a valid date: '{date_str}'. Expected format: YYYY-MM-DD.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AWS Billing Breakdown Script')
    parser.add_argument(
        '--start-date',
        type=parse_date,
        required=False,
        help='Start date in YYYY-MM-DD format (default: first day of the current month)'
    )
    parser.add_argument(
        '--end-date',
        type=parse_date,
        required=False,
        help='End date in YYYY-MM-DD format (default: today\'s date)'
    )
    parser.add_argument(
        '--metrics',
        nargs='+',
        default=['UnblendedCost'],
        help='Metrics to retrieve (default: UnblendedCost). Options: UnblendedCost, BlendedCost, UsageQuantity'
    )
    parser.add_argument(
        '--output-file',
        type=str,
        required=False,
        help='Output file path to save the billing data'
    )
    parser.add_argument(
        '--output-format',
        type=str,
        choices=['csv', 'json'],
        required=False,
        help='Output file format: csv or json (required if --output-file is specified)'
    )
    args = parser.parse_args()

    # Set default dates if not provided
    now = datetime.datetime.now(datetime.timezone.utc)
    if args.start_date:
        start_date = args.start_date
    else:
        start_date = now.replace(day=1).strftime('%Y-%m-%d')

    if args.end_date:
        end_date = args.end_date
    else:
        end_date = now.strftime('%Y-%m-%d')

    if args.output_file and not args.output_format:
        parser.error("--output-format is required when --output-file is specified.")

    response = get_billing_data(start_date, end_date, args.metrics)
    aggregated_data = aggregate_billing_data(response, args.metrics)
    print_billing_data(aggregated_data, args.metrics, start_date, end_date, args.output_file, args.output_format)
