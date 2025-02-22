from typing import List, Tuple, Dict
import numpy as np
from itertools import permutations

from tensor_network.tensor_network import TensorNetwork
from tensor_network.tensor_network import Node, Edge

class EfficientGaussianEmb:
    """
    A class that represents an efficient gaussian embedding for a tensor network.
    Implements the paper: https://arxiv.org/abs/2205.13163
    """

    def __init__(self, eps: float, delta: float, m_scalar: float, is_tn_embedding=False):
        """
        Creats the Efficient Gaussian Embedding object.
        The embedding is eps-delta accurate
        :param eps: The change in norm allowed for the sketching in a normalized vector
        :param delta: The probability for a higher change than epsilon
        :param m_scalar: The scalar to multiply m by in order to actually get good results.
        m=theta(N_E/log(1/delta)/eps^2) so we have m up to this scalar
        :param is_tn_embedding: Should we use TN or tree embedding
        """
        self.eps = eps
        self.delta = delta
        self.m_scalar = m_scalar
        self.is_tn_embedding = is_tn_embedding

    def calc_m(self, x: TensorNetwork):
        """
        We calculate the dimension size to sketch with
        :return: The dimensions size to sketch to
        """
        m_theta = len(x.get_edges_to_sketch()) * np.log(1 / self.delta) / self.eps ** 2
        m = int(m_theta * self.m_scalar)
        return max(m, 1)

    def embed(self, x: TensorNetwork, contraction_path: List[Tuple[int, int]]) -> TensorNetwork:
        """
        Embeds the tensor x using the paper "Cost-efficient Gaussian tensor network embeddings
        for tensor-structured inputs"
        :param x: The tensor network to embed
        :param contraction_path: The contraction path of x, T_0
        :return: An embedded tensor network
        """
        edges_to_be_sketched = x.get_edges_to_sketch()
        m = self.calc_m(x)

        D, S, I_S = self._partition_contractions(x, contraction_path, edges_to_be_sketched)
        self._contract_and_sketch_kronecker_product(x, D, m)
        self._contract_and_sketch_tree_embedding(S, I_S, x, m)
        return x

    def _partition_contractions(self, x: TensorNetwork, contraction_path: List[Tuple[int, int]],
                                edges_to_sketch):
        """
        Partitions the contractions for the sketching algorithm
        :param x: The tensor network to sketch
        :param contraction_path: The contraction path for the tensor network
        :param edges_to_sketch: Edges in E_1
        :return:  D - Dict of the format <i : List[Contractions]>. Where each tuple represents D(e_i)
                  S - A list of contractions with both nodes having dimensions to be sketched
                  I_S - A list of contractions with no nodes to be sketched union with S
        """
        D = {e: [] for e in edges_to_sketch}
        S = []
        I_S = []

        for contraction in contraction_path:
            u_i = x[contraction[0]]
            v_i = x[contraction[1]]

            u_i_dangling = u_i.get_all_dangling()
            v_i_dangling = v_i.get_all_dangling()

            u_i_dims_to_sketch = len(u_i_dangling)
            v_i_dims_to_sketch = len(v_i_dangling)

            if u_i_dims_to_sketch and v_i_dims_to_sketch:
                S.append(contraction)
                I_S.append(contraction)
            elif u_i_dims_to_sketch == 1:
                D[u_i_dangling[0]].append(contraction)
            elif v_i_dims_to_sketch == 1:
                D[v_i_dangling[0]].append(contraction)
            else:
                I_S.append(contraction)
        return D, S, I_S

    def _contract_and_sketch_kronecker_product(self, x: TensorNetwork, D: Dict[Edge, List[Tuple[int, int]]],
                                               m: int) -> None:
        """
        Sketcghes the kroncker product part of the algorithm and contracts when necessary
        :param x: The tensor network to contract
        :param D: A dict where each tuple represents D(e_i)
        :param m: sketch dimension size
        """
        for e, D_e_i in D.items():
            if len(D_e_i) == 0:
                x.sketch(edge=e, m=m)
            else:
                e_i_hat_node_index = x.get_node_index(e.node1)
                minimal_contraction_path = self._calculate_contraction_path_shapes(x, D_e_i, e_i_hat_node_index)
                for i, j in minimal_contraction_path:
                    if j is None:
                        x.sketch(edge=e, m=m)
                    else:
                        x.contract(i, j)

    def _calculate_contraction_path_shapes(self, x: TensorNetwork, D_e_i: List[Tuple[int, int]], i: int):
        """
        Calculates for a list of contraction of the form D_e_i when to add the sketching so we will have a minimal
        sketching cost. i.e. how to contract the sub tensor network such that node_e_i has minimal size to sketch
        :param x: The tensor network
        :param D_e_i: A list of contraction where each tuple if of the form {i, j} where i is the node to minimize
        :param i: The node index to minimize the computations on
        :return: A reordering of the contractions list with an added (i, None) for the sketching adding
        """
        u = x[i]

        j_nodes = [u if v == i else v for u, v in D_e_i]

        contractions_permutations = list(permutations(j_nodes))
        u_possible_sizes = []
        u_possible_sketching_index = []
        for permutation in contractions_permutations:
            contraction_nodes = [x[i] for i in permutation]
            min_u_size, min_u_size_index = self._contraction_path_minimize_U(u, contraction_nodes)
            u_possible_sizes.append(min_u_size)
            u_possible_sketching_index.append(min_u_size_index)

        chosen_path_index = np.argmin(u_possible_sizes)
        sketch_index = u_possible_sketching_index[chosen_path_index]
        chosen_path = list(contractions_permutations[chosen_path_index])
        chosen_path.insert(sketch_index + 1, None)
        return list(zip([i] * len(chosen_path), chosen_path))

    @staticmethod
    def _contraction_path_minimize_U(U: Node, contraction_order: List[Node]):
        """
        Calculates with a given contraction path, what is the minimal size U gets here and where
        :param U: The node to minimize
        :param contraction_order: List of nodes to contract with U in the specified order
        :return: Minimum size of U reached during contractions and the index where this occurs
        """
        min_U_size = U.tensor.size
        min_index = -1
        current_shape = U.tensor.shape

        U_edges = {edge: current_shape[i] for i, edge in enumerate(U.edges)}

        for i, V in enumerate(contraction_order):
            contracted_indices = []
            for edge in U.edges:
                if edge in V.edges:
                    contracted_indices.append(U_edges[edge])

            new_shape = [dim for dim in current_shape if dim not in contracted_indices]
            new_shape += [dim for dim in V.tensor.shape if dim not in contracted_indices]


            new_U_size = np.prod(new_shape)
            current_shape = new_shape
            if new_U_size < min_U_size:
                min_U_size = new_U_size
                min_index = i

        return min_U_size, min_index


    def _contract_and_sketch_tree_embedding(self, S, I_S, x, m) -> None:
        """
        Contracts and sketches the tree embedding part of the algorithm.
        i.e. contractions in S are sketched in a specific way with a tree like embedding and contractions in
        I are simply contracted
        :param S: The contractions to be tree embedded
        :param I_S: All contractions to make
        :param x: The tensornetwork
        :param m: The sketch dimension size
        """
        for i, j in I_S:
            if (i, j) in S:
                if self.is_tn_embedding:
                    x.tn_sketch_and_contract_s(i, j, m)
                else:
                    x.tree_sketch_and_contract(i, j, m)
            else:
                x.contract(i, j)
