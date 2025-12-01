from inference import process_id

# Process an Aadhaar back image
result = process_id(
    image_path="samples/manish_aadhar.jpeg",
    save_json=True,
    output_json="manish_aadhar.json",
    verbose=True
)

# Print results
import json
print(json.dumps(result, indent=2))
