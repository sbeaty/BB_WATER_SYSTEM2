from sql_historian_client import SQLHistorianClient, HistorianConfig

config = HistorianConfig(
    server='192.168.10.236', 
    database='Runtime', 
    username='wwUser', 
    password='wwUser'
)

client = SQLHistorianClient(config)
client.connect()

print("Getting available tags...")
tags = client.get_available_tags()
print(f"Found {len(tags)} tags")

print("\nLooking for FT tags:")
ft_tags = [tag for tag in tags if 'FT' in tag.upper()]
for tag in ft_tags[:20]:  # Show first 20 FT tags
    print(f"  {tag}")

client.disconnect()
