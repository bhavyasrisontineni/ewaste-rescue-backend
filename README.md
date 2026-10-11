# E-Waste Rescue — Backend Starter

This is a small AWS Lambda/Python starter for an e-waste image-upload workflow.

## What works in this starter

- `GET /health` — health check
- `POST /upload-url` — creates a short-lived S3 presigned upload URL
- `POST /classify` — checks the uploaded image, returns a **placeholder** category and disposal guidance, and stores a scan record in DynamoDB
- `GET /disposal-guide/{category}` — returns disposal guidance

**Important:** classification is currently a filename-based placeholder, not AI image recognition. It does not inspect the pixels. Connect a trained/deployed SageMaker model before presenting classification as AI.

## AWS resources to create

Use the same AWS Region for all resources.

1. **S3 bucket** for uploads. Block all public access. Enable default encryption. Keep Object Ownership as bucket owner enforced.
2. **DynamoDB table** named `EWasteScans`, partition key `scanId` (String).
3. **Lambda function** named `ewaste-rescue-api`, runtime Python 3.12 or another currently supported Python runtime.
4. **HTTP API** in API Gateway with routes:
   - `GET /health`
   - `POST /upload-url`
   - `POST /classify`
   - `GET /disposal-guide/{category}`
   Integrate all routes with the Lambda function. Add an `OPTIONS /{proxy+}` route or configure CORS in API Gateway as needed.
5. Set Lambda environment variables:
   - `UPLOAD_BUCKET` = your private S3 bucket name
   - `SCAN_TABLE` = `EWasteScans`
   - `CORS_ORIGIN` = your frontend URL (use `*` only during local testing)

## Lambda execution role permissions

Attach CloudWatch Logs permissions and grant only the following data access to this function:
- S3: `s3:PutObject` on `arn:aws:s3:::YOUR_BUCKET/uploads/*` (presigned upload), plus `s3:HeadObject`/`s3:GetObject` as required for checking uploaded objects.
- DynamoDB: `dynamodb:PutItem` on the `EWasteScans` table.

Do not make the S3 bucket public. Do not put AWS access keys in frontend code.

## Request examples

### 1. Create upload URL

`POST /upload-url`

```json
{
  "filename": "phone.jpg",
  "contentType": "image/jpeg",
  "sizeBytes": 123456
}
```

The response includes `uploadUrl`, `s3Key`, and `scanId`.

### 2. Upload the image from the frontend

Send a `PUT` request to the returned `uploadUrl` with the image file as the raw request body and the same `Content-Type` header returned by the API. Do not send JSON for this PUT.

### 3. Classify the uploaded image

`POST /classify`

```json
{
  "scanId": "the-scan-id-from-upload-url",
  "s3Key": "uploads/the-scan-id/phone.jpg"
}
```

### 4. Get disposal guide

`GET /disposal-guide/battery`

Supported categories:
- `mobile_phone`
- `battery`
- `charger_or_cable`
- `laptop_or_computer`
- `other_e_waste`

## Security and production checklist

- Configure Cognito JWT authorization on API Gateway before exposing user history or user-specific records.
- Restrict CORS to the actual frontend domain.
- Validate file signatures as well as content type before production.
- Add throttling and request limits in API Gateway.
- Avoid logging personal data or presigned URLs.
- Add a user identity field to DynamoDB records when Cognito is integrated; do not trust a user ID supplied by the browser.
- For a real AI prediction, deploy a model to SageMaker and call it from Lambda using `sagemaker:InvokeEndpoint`.
- Use Google Places API from a backend endpoint and keep the API key in Secrets Manager or a protected Lambda environment, with API restrictions enabled.

## Suggested implementation order

1. Get `/health` working.
2. Test `/upload-url`, upload to S3, then call `/classify`.
3. Connect the frontend.
4. Add SageMaker inference.
5. Add Cognito and user-specific history.
6. Add Google Places recycling-center lookup.
