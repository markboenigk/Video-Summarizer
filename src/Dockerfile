# Use the official AWS Lambda Python runtime as the base image
FROM public.ecr.aws/lambda/python:3.11

# Set the working directory inside the container
WORKDIR /app

# Copy only the necessary Python files (lambda_function.py, instagram_utils.py) to the container
COPY lambda_function.py .

COPY utils/ utils/

# Copy the requirements.txt file
COPY requirements.txt .
COPY transcription_output.txt .

COPY prompts/ prompts/

# Install any Python dependencies listed in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set the environment variable for Lambda function handler
ENV LAMBDA_TASK_ROOT=/app

# Set the default command to call the Lambda function handler
CMD ["lambda_function.lambda_handler"]
