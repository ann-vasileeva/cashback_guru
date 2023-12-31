import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
import scipy.sparse as sp
from sklearn.preprocessing import LabelEncoder


class StupidRecommender:
    def init(self) -> None:
        pass

    def fit(self):
        pass

    def predict(self, user_id, users, items, interactions, k=1):
        users_fav_categories = users.loc[user_id, 'categories']
        if pd.isna(users_fav_categories):
            users_fav_categories = []
        else:
            users_fav_categories = users_fav_categories.split(';')
        if users.loc[user_id, 'kids_flag'] == 1:
            users_fav_categories.append('Товары для детей')
        if users.loc[user_id, 'pets_flag'] == 1:
            users_fav_categories.append('Товары для животных')

        items_from_fav_categ = items.loc[items['category'].isin(users_fav_categories), 'item_id'].values.tolist()
        rest_items = items.loc[~items['category'].isin(users_fav_categories), 'item_id'].values.tolist()
        n_fav = len(items_from_fav_categ)
        n_rest = len(items) - n_fav

        probs = [2] * n_fav + [1] * n_rest
        probs = probs / np.sum(probs)

        sampled_items = np.random.choice(items_from_fav_categ + rest_items, size=10, p=probs, replace=False)
        used_items = interactions.loc[interactions['user_id'] == user_id, 'item_id'].values
        filtered_items = np.setdiff1d(sampled_items, used_items, assume_unique=True)

        if k == 1:
            return filtered_items[0] if len(filtered_items) else -1
        else:
            return filtered_items[:k]


class EASE:
    def __init__(self, reg: float = 0.01, window=80) -> None:
        self.reg = reg
        self.trained = False
        self.item_similarity = None
        self.interaction_matrix = None
        self.user_encoder = None
        self.item_encoder = None
        self.window = window
        self.n_items = 116
        self.item_encoder = LabelEncoder().fit(np.arange(self.n_items))

    def fit(
            self, df, items, item_col='item_id', user_col="user_id", value_col='feedback'
    ) -> None:
        # user_ids = df[user_col].unique()
        # item_ids = df[item_col].unique()

        self.user_encoder = LabelEncoder().fit(df[user_col].unique())
        # self.item_encoder = LabelEncoder().fit(items[item_col])

        uniq_ids = df[[user_col, item_col]].drop_duplicates(keep='last').index
        user_ids = self.user_encoder.transform(df.loc[uniq_ids, user_col])
        item_ids = self.item_encoder.transform(df.loc[uniq_ids, item_col])

        # counts = np.ones(len(uniq_ids))
        # counts = df.loc[uniq_ids, value_col].values
        vals = df.loc[uniq_ids]
        vals.loc[vals[value_col] == 0, value_col] = -1
        counts = vals[value_col].values

        n_users = df[user_col].nunique()
        matrix_shape = n_users, self.n_items

        X = csr_matrix((counts, (user_ids, item_ids)), shape=matrix_shape)

        G = X.T @ X
        G += self.reg * sp.identity(G.shape[0]).astype(np.float32)
        G = G.todense()
        P = np.linalg.inv(G)
        B = P / (-np.diag(P))
        np.fill_diagonal(B, 0.0)

        self.item_similarity = B
        self.interaction_matrix = X
        self.trained = True

    def predict(self, user_id, interactions, k=1):
        assert self.trained

        encoded_user_id = self.user_encoder.transform([user_id])[0]
        scores = self.interaction_matrix[encoded_user_id, :] @ self.item_similarity
        ids = np.argsort(-scores, axis=-1)
        orig_item_ids = self.item_encoder.inverse_transform(np.array(ids)[0])
        # print('all ids' orig_item_ids[:5], len(orig_item_ids)) 

        used_items = interactions.loc[interactions['user_id'] == user_id, 'item_id'].drop_duplicates(keep='last')
        used_items = used_items[-self.window:]
        filtered_items = np.setdiff1d(orig_item_ids, used_items, assume_unique=True)

        if k == 1:
            return filtered_items[0] if len(filtered_items) else -1
        else:
            return filtered_items[:k]
