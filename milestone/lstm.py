import torch
import torch.utils.data
import os
import numpy as np
import sys
sys.path.append('./processing_scripts/')
from simple_processing import load_simple_array


class TrajectoryPredictor:

  def __init__(self, input_dim, output_dim, batch_size):

    self.input_dim = input_dim
    self.output_dim = output_dim
    self.batch_size = batch_size

    self.lstm = torch.nn.LSTM(input_dim, output_dim)

  # tensors should be sequence_len x batch_size x input_dim
  def train(self, train_loader, num_epochs):

    loss_function = torch.nn.PairwiseDistance()
    optimizer = torch.optim.Adam(self.lstm.parameters())

    for epoch in range(num_epochs):   
      total_loss = 0.0
      count = 0
      for data in train_loader:

        optimizer.zero_grad()
        traj_first_part, traj_second_part = data
        traj_first_part, traj_second_part = torch.autograd.Variable(traj_first_part), \
                                            torch.autograd.Variable(traj_second_part)

        first_part_len = int(traj_first_part.size()[1])
        second_part_len = int(traj_second_part.size()[1])

        actual_batch_size = min(int(traj_first_part.size()[0]), self.batch_size)
        count += actual_batch_size

        self.init_state(actual_batch_size)

        for i in range(first_part_len):
          inp = traj_first_part[:,i,:].contiguous().view(1, actual_batch_size, self.input_dim)
          out, self.state = self.lstm(inp, self.state)

        second_part_preds = [out.contiguous().view(actual_batch_size, 1, self.output_dim)]
        
        for i in range(second_part_len-1):
          inp = traj_second_part[:,i,:].contiguous().view(1, actual_batch_size, self.input_dim)

          pred, self.state = self.lstm(inp, self.state)
          second_part_preds.append(pred.contiguous().view(actual_batch_size, 1, self.output_dim))

        second_part_preds = torch.cat(second_part_preds, dim=1)

        ground_truth_points = traj_second_part.contiguous().view(-1, self.output_dim)
        pred_points = second_part_preds.contiguous().view(-1, self.output_dim)

        loss = loss_function(ground_truth_points, pred_points).sum()
        loss.backward()

        total_loss += loss.data[0]

        optimizer.step()

      mean_loss = total_loss / count
      print("epoch %s. mean loss: %s" % (epoch+1, mean_loss))

  def test(self, test_loader):
    
    loss_function = torch.nn.PairwiseDistance()
    total_loss = 0.0

    count = 0

    for data in test_loader:

      traj_first_part, traj_second_part = data
      traj_first_part, traj_second_part = torch.autograd.Variable(traj_first_part), \
                                          torch.autograd.Variable(traj_second_part)

      first_part_len = int(traj_first_part.size()[1])
      second_part_len = int(traj_second_part.size()[1])

      actual_batch_size = min(int(traj_first_part.size()[0]), self.batch_size)

      count += actual_batch_size

      self.init_state(actual_batch_size)


      for i in range(first_part_len):
        inp = traj_first_part[:,i,:].contiguous().view(1, actual_batch_size, self.input_dim)
        out, self.state = self.lstm(inp, self.state)

      second_part_preds = [out.contiguous().view(actual_batch_size, 1, self.output_dim)]

      for i in range(second_part_len-1):
        out, self.state = self.lstm(out, self.state)
        second_part_preds.append(out.contiguous().view(actual_batch_size, 1, self.output_dim))

      second_part_preds = torch.cat(second_part_preds, dim=1)

      ground_truth_points = traj_second_part.contiguous().view(-1, self.output_dim)
      pred_points = second_part_preds.contiguous().view(-1, self.output_dim)

      loss = loss_function(ground_truth_points, pred_points).sum()
      total_loss += loss.data[0]

    mean_loss = total_loss / count
    print("mean loss: %s" % (mean_loss))

  def init_state(self, batch_size):
    # first dimension is number of layers
    h_init = torch.autograd.Variable(torch.zeros(1, batch_size, self.output_dim))
    c_init = torch.autograd.Variable(torch.zeros(1, batch_size, self.output_dim))

    self.state = (h_init, c_init)

if __name__ == '__main__':
  train_trajectories1 = []
  train_trajectories2 = []
  for dirname in os.listdir('train_data'):
    if dirname == 'stanford':
      for filename in os.listdir('train_data/' + dirname):
        if filename.endswith('.txt'):
          trajectories = load_simple_array('train_data/' + dirname + '/' + filename)
          train_trajectories1 += [traj[:10,:] for traj in trajectories]
          train_trajectories2 += [traj[10:,:] for traj in trajectories]
  
  print len(train_trajectories1)
  train_trajectories1 = np.stack(train_trajectories1)
  train_trajectories2 = np.stack(train_trajectories2)
  data_tensor = torch.Tensor(train_trajectories1)
  target_tensor = torch.Tensor(train_trajectories2)

  dataset = torch.utils.data.TensorDataset(data_tensor, target_tensor)

  batch_size = 4
  num_epochs = 40

  train_loader = torch.utils.data.DataLoader(dataset, batch_size)
  test_loader = torch.utils.data.DataLoader(dataset, batch_size)

  p = TrajectoryPredictor(2, 2, batch_size)
  p.train(train_loader, num_epochs)

  loss = p.test(test_loader)

  print loss
