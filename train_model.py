# train_model.py
import torch
import torch.nn as nn
import torch.optim as optim
from model import TrafficLSTM
import numpy as np

def load_training_data():
    # Dummy data: 1000 samples, sequence length 24, 10 features
    num_samples = 1000
    seq_len = 24
    input_dim = 10
    X = np.random.rand(num_samples, seq_len, input_dim).astype(np.float32)
    y = np.random.rand(num_samples, 1).astype(np.float32)
    return X, y

def main():
    X, y = load_training_data()
    X = torch.from_numpy(X)
    y = torch.from_numpy(y)
    
    model = TrafficLSTM(input_dim=10, hidden_dim=32, output_dim=1)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    epochs = 10

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        outputs = model(X)
        loss = criterion(outputs, y)
        loss.backward()
        optimizer.step()
        print(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")

    torch.save(model.state_dict(), "traffic_model.pth")
    print("Model saved as traffic_model.pth")

if __name__ == '__main__':
    main()
