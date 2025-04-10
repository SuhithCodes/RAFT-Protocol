FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py .
COPY *.proto .

RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. raft.proto

CMD ["python", "node.py"]

FROM node:16-slim

WORKDIR /app

# Install protobuf compiler and other dependencies
RUN apt-get update && apt-get install -y \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

# Install npm dependencies
COPY package*.json ./
RUN npm install

# Copy source files
COPY . .

# Generate gRPC code
RUN protoc \
    --js_out=import_style=commonjs,binary:. \
    --grpc_out=grpc_js:. \
    --plugin=protoc-gen-grpc=./node_modules/.bin/grpc_tools_node_protoc_plugin \
    raft.proto

CMD ["npm", "start"] 

