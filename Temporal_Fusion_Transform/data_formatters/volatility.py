import pandas as pd
from .utils2 import get_single_col_by_input_type
from .utils2 import extract_cols_from_data_type
from .base import GenericDataFormatter
from .base import DataTypes, InputTypes
import sklearn.preprocessing

class VolatilityFormatter(GenericDataFormatter):
    """Defines and formats data for the volatility dataset.
    Attributes:
    column_definition: Defines input and data type of column used in the
      experiment.
    identifiers: Entity identifiers used in experiments.
    """

    _column_definition = [
        
       ('PRICE_ASK_0', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('PRICE_BID_0', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('VOLUME_ASK_0', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('VOLUME_BID_0', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('SPREAD', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('midprice', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('id', DataTypes.REAL_VALUED, InputTypes.ID),
        ('time', DataTypes.REAL_VALUED, InputTypes.TIME),
        ('rolling_volatility', DataTypes.REAL_VALUED, InputTypes.TARGET),
        ('STOCK', DataTypes.CATEGORICAL, InputTypes.STATIC_INPUT),

    ]

    def __init__(self):
        """Initialises formatter."""

        self.identifiers = None
        self._real_scalers = None
        self._cat_scalers = None
        self._target_scaler = None
        self._num_classes_per_cat_input = None
        self._time_steps = self.get_fixed_params()['total_time_steps']
        self._num_encoder_steps = self.get_fixed_params()['num_encoder_steps']
        
    def get_time_steps(self):
        return self.get_fixed_params()['total_time_steps']
    
    def get_num_encoder_steps(self):
        return self.get_fixed_params()['num_encoder_steps']

    def split_data(self, df, valid_boundary=7, test_boundary=8):
        """Splits data frame into training-validation-test data frames.
        This also calibrates scaling object, and transforms data for each split.
        Args:
          df: Source data frame to split.
          valid_boundary: Starting year for validation data
          test_boundary: Starting year for test data
        Returns:
          Tuple of transformed (train, valid, test) data.
        """

        print('Formatting train-valid-test splits.')

        index = df['DAY']
        train = df.loc[index < valid_boundary]
        valid = df.loc[(index >= valid_boundary) & (index < test_boundary)]
        test = df.loc[index >= test_boundary]

        self.set_scalers(train)

        return (self.transform_inputs(data) for data in [train, valid, test])

    def set_scalers(self, df):
        """Calibrates scalers using the data supplied.
        Args:
          df: Data to use to calibrate scalers.
        """
        print('Setting scalers with training data...')

        column_definitions = self.get_column_definition()
        id_column = get_single_col_by_input_type(InputTypes.ID,
                                                       column_definitions)
        target_column = get_single_col_by_input_type(InputTypes.TARGET,
                                                           column_definitions)
       
        # Extract identifiers in case required
        self.identifiers = list(df[id_column].unique())

        # Format real scalers
        real_inputs = extract_cols_from_data_type(
            DataTypes.REAL_VALUED, column_definitions,
            {InputTypes.ID, InputTypes.TIME})

        data = df[real_inputs].values
       
        self._real_scalers = sklearn.preprocessing.StandardScaler().fit(data)
        self._target_scaler = sklearn.preprocessing.StandardScaler().fit(
            df[[target_column]].values)  # used for predictions

        # Format categorical scalers
        categorical_inputs = extract_cols_from_data_type(
            DataTypes.CATEGORICAL, column_definitions,
            {InputTypes.ID, InputTypes.TIME})

        categorical_scalers = {}
        num_classes = []
        for col in categorical_inputs:
            # Set all to str so that we don't have mixed integer/string columns
            srs = df[col].apply(str)
            categorical_scalers[col] = sklearn.preprocessing.LabelEncoder().fit(
              srs.values)
            num_classes.append(srs.nunique())

        # Set categorical scaler outputs
        self._cat_scalers = categorical_scalers
        self._num_classes_per_cat_input = num_classes

    def transform_inputs(self, df):
        """Performs feature transformations.
        This includes both feature engineering, preprocessing and normalisation.
        Args:
          df: Data frame to transform.
        Returns:
          Transformed data frame.
        """
        output = df.copy()

        if self._real_scalers is None and self._cat_scalers is None:
            raise ValueError('Scalers have not been set!')

        column_definitions = self.get_column_definition()

        real_inputs = extract_cols_from_data_type(
            DataTypes.REAL_VALUED, column_definitions,
            {InputTypes.ID, InputTypes.TIME})
        categorical_inputs = extract_cols_from_data_type(
            DataTypes.CATEGORICAL, column_definitions,
            {InputTypes.ID, InputTypes.TIME})

        # Format real inputs
        output[real_inputs] = self._real_scalers.transform(df[real_inputs].values)

        # Format categorical inputs
        for col in categorical_inputs:
            string_df = df[col].apply(str)
            output[col] = self._cat_scalers[col].transform(string_df)

        return output

    def format_predictions(self, predictions):
        """Reverts any normalisation to give predictions in original scale.
        Args:
          predictions: Dataframe of model predictions.
        Returns:
          Data frame of unnormalised predictions.
        """
        output = predictions.copy()

        column_names = predictions.columns

        for col in column_names:
            if col not in {'forecast_time', 'identifier'}:
                output[col] = self._target_scaler.inverse_transform(predictions[col])

        return output

    def get_fixed_params(self, forecast_horizon=20):
        """Returns fixed model parameters for experiments.

        Args:
            forecast_horizon (int): The forecast horizon for prediction.

        Returns:
            dict: Fixed parameters for the model.
        """
        fixed_params = {
            'total_time_steps': 100 + forecast_horizon,
            'num_encoder_steps': 100,
            'num_epochs': 100,
            'early_stopping_patience': 5,
            'multiprocessing_workers': 5,
        }
        return fixed_params
    def get_default_model_params(self):
        """Returns default optimised model parameters."""

        model_params = {
            'dropout_rate': 0.3,
            'hidden_layer_size': 160,
            'learning_rate': 0.01,
            'minibatch_size': 64,
            'max_gradient_norm': 0.01,
            'num_heads': 1,
            'stack_size': 1
        }

        return model_params