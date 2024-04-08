import os
from repomap import RepoMap

if __name__ == "__main__":
  test_file_ts = "file1.ts"
  temp_dir = "test_files"
  other_files = [os.path.join(temp_dir, test_file_ts)]
  repo_map = RepoMap(root=temp_dir)
  result = repo_map.get_repo_map(other_files)
  print(result)