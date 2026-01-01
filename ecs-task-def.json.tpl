{
  "family": "REPLACE_TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "REPLACE_EXECUTION_ROLE_ARN",
  "taskRoleArn": "REPLACE_TASK_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "REPLACE_CONTAINER_NAME",
      "image": "REPLACE_IMAGE_URI",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        { "name": "DB_HOST", "value": "REPLACE_DB_HOST" },
        { "name": "DB_USER", "value": "REPLACE_DB_USER" },
        { "name": "DB_NAME", "value": "REPLACE_DB_NAME" }
      ],
      "secrets": [
        { "name": "DB_PASSWORD", "valueFrom": "REPLACE_SECRETS_MANAGER_ARN_FOR_DB_PASSWORD" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "REPLACE_LOG_GROUP",
          "awslogs-region": "REPLACE_REGION",
          "awslogs-stream-prefix": "portal"
        }
      }
    }
  ]
}