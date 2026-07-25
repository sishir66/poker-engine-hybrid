import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import joblib
from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt


class PokerMLP(nn.Module):
    def __init__(self):
        super(PokerMLP, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(14, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.2),

            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),

            nn.Linear(256, 128),
            nn.ReLU(),

            nn.Linear(128, 10)
        )

    def forward(self, x):
        return self.network(x)


def perform_intervention_check(model, X_test, y_test):
    model.eval()
    with torch.no_grad():
        outputs = model(X_test)
        _, predicted = torch.max(outputs, 1)
    cm = confusion_matrix(y_test, predicted)
    plt.figure(figsize=(10, 8))
    hand_labels = ['High Card', 'Pair', 'Two Pair', 'Trips', 'Straight',
                   'Flush', 'Full House', 'Quads', 'St. Flush', 'Royal Flush']
    sns.heatmap(cm, annot=True, fmt='d', cmap='magma',
                xticklabels=hand_labels, yticklabels=hand_labels)
    plt.xlabel('What the AI Predicted')
    plt.ylabel('The Actual Hand Label')
    plt.title('Poker Model Error Map')
    plt.show()


def train():
    print("Loading data...")
    df = pd.read_csv('data/poker_training_daa_v1.csv')
    X = df.drop('Label', axis=1).values
    y = df['Label'].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    joblib.dump(scaler, 'data/poker_scaler.pkl')

    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

    X_train = torch.FloatTensor(X_train)
    y_train = torch.LongTensor(y_train)
    X_test  = torch.FloatTensor(X_test)
    y_test  = torch.LongTensor(y_test)

    weights = torch.tensor([0.5, 1.0, 2.0, 5.0, 3.0, 8.0, 5.0, 10.0, 15.0, 20.0])

    model = PokerMLP()
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    print("Starting training...")
    for epoch in range(101):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train)
        loss = criterion(outputs, y_train)
        loss.backward()
        optimizer.step()

        if epoch % 10 == 0:
            model.eval()
            with torch.no_grad():
                test_outputs = model(X_test)
                _, predicted = torch.max(test_outputs, 1)
                accuracy = (predicted == y_test).sum().item() / len(y_test)
                print(f"Epoch {epoch} | Loss: {loss.item():.4f} | Test Accuracy: {accuracy*100:.2f}%")

    torch.save(model.state_dict(), 'data/poker_model.pth')
    print("Model saved to data/poker_model.pth")
    perform_intervention_check(model, X_test, y_test)


if __name__ == "__main__":
    train()
