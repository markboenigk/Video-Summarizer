# Video-Summarizer
Welcome to the Video Summarizer Bot repository! I created a bot that extracts information from videos (in this case Instagram Reels) by transcribing and summarizing them using Open AI's Whisper and GPT-4o-mini model. Users can enter a reel url in the telegram chat and then the bot transcribes the video and summarizes it and then sends a summary back to the user. 

I created that bot because i came across many informational reels on Instagram that provided me with a lot of value. With that bot I automated the information extraction and don't have to make notes in a time consuming manner or have to rely on thired party tools. 

## 💻 Tech Stack

<ul> 
  <li>Compute: AWS Lambdas (with Docker) </li>
  <li>Storage: AWS S3 and Dynamo DB</li>
  <li>API: AWS API Gateway </li>
  <li>Configuration / Secret Management : AWS AppConfig & Secrets Manager </li>
  <li>Testing: Postman / Docker </li>
</ul>

## Docker Container Structure 
The docker container is accessing the following files and modules: 
```.
├── Dockerfile
├── lambda_function.py -- executes the code and handles messages 
├── prompts -- contains the prompts to classify and summarize the content
│   ├── classification_prompt.txt
│   ├── company_summary_prompt.txt
│   ├── summary_prompt.txt
│   └── technology_summary_prompt.txt
├── requirements.txt
└── utils 
    ├── __init__.py
    ├── aws_utils.py -- Functions to interact with AWS 
    ├── instagram_utils.py -- Download and process reel
    ├── send_message_utils.py -- Message templates and functions 
    ├── summary_utils.py -- Open AI functions to sumamrize the transcription
    └── transcription_utils.py-- Open AI functions to transcribe the video
```

## 🔧 Usage 

1. Build docker container ```docker build -t video-summarizer .```
2. Create API endpoint with AWS API Gateway, connect Lambda function as the target
3. Register Telegram bot webhook with API endpoint 
4. Push the local docker image to AWS Elastic Container Registry (ECR) so AWS Lambda can access the image.
5. Send reel url in chat with telegram bot

## 📌 Disclaimer
This project is intended for personal and educational use only.

It may include tools or scripts that transcribe or analyze publicly accessible Instagram Reels. All content remains the property of the original creators and Instagram. This project does not download, distribute, or republish any copyrighted material.

By using this project, you agree to:

Use it only for private, non-commercial purposes.
Respect Instagram's Terms of Use and content ownership rights.
Not share, post, or monetize any transcriptions or summaries generated from third-party content.
This repository is not affiliated with, endorsed by, or connected to Instagram or Meta Platforms, Inc.

## License
This project is licensed under the MIT License.
