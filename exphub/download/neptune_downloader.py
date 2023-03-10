from exphub.download.downloader import Downloader
import pandas as pd
from typing import Optional, Union, List
import os
import neptune.new as neptune


class NeptuneDownloader(Downloader):
    NEPTUNE_API_TOKEN = 'NEPTUNE_API_TOKEN'

    def __init__(self, project_name: str, api_token: Optional[str] = None):
        """Initialize a NeptuneDownloader instance.

        Args:
            project_name (str): The name of the Neptune project to download data from.
            api_token (Optional[str], optional): The API token for the Neptune project. If not provided,
                the method will attempt to use the `NEPTUNE_API_TOKEN` environment variable. Defaults to None.

        Raises:
            ValueError: If the `api_token` argument is not provided and the `NEPTUNE_API_TOKEN` environment variable
                is not set.
        """
        self.api_token = api_token
        self.project_name = project_name
        if self.api_token is None:
            if NeptuneDownloader.NEPTUNE_API_TOKEN not in os.environ:
                raise ValueError(f'Environment variable {NeptuneDownloader.NEPTUNE_API_TOKEN} not found.')
            self.api_token = os.environ[NeptuneDownloader.NEPTUNE_API_TOKEN]
        else:
            self.api_token = api_token
            os.environ[NeptuneDownloader.NEPTUNE_API_TOKEN] = api_token
        self.project = neptune.init_project(name=self.project_name, mode="read-only", api_token=self.api_token)

    def download(self,
                 id: Optional[Union[str, List[str]]] = None,
                 state: Optional[Union[str, List[str]]] = None,
                 owner: Optional[Union[str, List[str]]] = None,
                 tag: Optional[Union[str, List[str]]] = None,
                 columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Download a table of runs from a Neptune project.

        Args:
            id (Optional[Union[str, List[str]]]): A list of run IDs or a single run ID to filter the results by.
            state (Optional[Union[str, List[str]]]): A list of run states or a single run state to filter the results by.
            owner (Optional[Union[str, List[str]]]): A list of run owners or a single run owner to filter the results by.
            tag (Optional[Union[str, List[str]]]): A list of run tags or a single run tag to filter the results by.
            columns (Optional[List[str]]): A list of columns to include in the resulting table.

        Returns:
            pd.DataFrame: A Pandas DataFrame containing the resulting table of runs.
        """
        if all([id is None, state is None, owner is None, tag is None]):
            raise ValueError('At least one of id, state, owner, or tag must be provided.')
        return self.project.fetch_runs_table(owner=owner, id=id, state=state, tag=tag, columns=columns).to_pandas()

    def download_series(self,
                        series_column: Union[List[str], str],
                        id: Optional[Union[str, List[str]]] = None,
                        state: Optional[Union[str, List[str]]] = None,
                        owner: Optional[Union[str, List[str]]] = None,
                        tag: Optional[Union[str, List[str]]] = None) -> pd.DataFrame:
        """Download a table of runs from a Neptune project.

        Args:
            series_column (str): The name of the series column to download.
            id (Optional[Union[str, List[str]]]): A list of run IDs or a single run ID to filter the results by.
            state (Optional[Union[str, List[str]]]): A list of run states or a single run state to filter the results by.
            owner (Optional[Union[str, List[str]]]): A list of run owners or a single run owner to filter the results by.
            tag (Optional[Union[str, List[str]]]): A list of run tags or a single run tag to filter the results by.
            columns (Optional[List[str]]): A list of columns to include in the resulting table.

        Returns:
            pd.DataFrame: A Pandas DataFrame containing the resulting table of runs.
        """
        if all([id is None, state is None, owner is None, tag is None]):
            raise ValueError('At least one of id, state, owner, or tag must be provided.')

        ids = self.project.fetch_runs_table(
            owner=owner, id=id, state=state, tag=tag, columns='sys/id').to_pandas()['sys/id'].values

        # Run initialization
        runs = [
            neptune.init_run(project=self.project_name, with_id=run_id, mode="read-only", api_token=self.api_token)
            for run_id in ids
        ]

        def _fetch_values(col_label):
            print('Fetching values for column', col_label)
            if isinstance(col_label, list):
                assert len(col_label) == 1
                col_label = col_label[0]
            
            # Fetching values and counting the number of values
            id2value = {}
            missing = 0
            for id, run in zip(ids, runs):
                try:
                    id2value[id] = run[col_label].fetch_values(include_timestamp=False)
                except neptune.exceptions.NeptuneException:
                    print(f'[WARNING] Run {id} does not have a column named {col_label}')
                    missing += 1
            if missing == len(ids):
                raise ValueError(f'No runs have a column named {col_label}')
                    
            df = pd.DataFrame({})

            for id, value in id2value.items():
                df[f'{col_label}_{id}'] = value['value']

            return df

        if isinstance(series_column, str) or len(series_column) == 1:
            return _fetch_values(series_column)
        else:
            assert isinstance(series_column, list)
            dfs = [_fetch_values(col_label) for col_label in series_column]
            df = dfs[0]
            for d in dfs[1:]:
                df = df.join(d)
