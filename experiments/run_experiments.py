import os

from experiments.kroncker_experiments import KroneckerDataTester
from experiments.tt_experiments import TTDataTester

from experiments.analyze_results import AnalyzeResults

def create_folders():
    """
    Creates the folders to save the data and graphs in
    """
    os.makedirs("./results/graphs", exist_ok=True)
    os.makedirs("./results/kronecker_order_test", exist_ok=True)
    os.makedirs("./results/tt_rank_test", exist_ok=True)


if __name__ == "__main__":
    # Create folders
    create_folders()

    # Run Kronecker Experiments
    order = [4, 5, 6, 7, 8]
    m_scalar_options = [4, 5, 6, 7]
    katri_rao_sketch_sizes = [1000, 3000, 5000, 10 ** 4, 15000, 20000]
    kroncker_data_tester = KroneckerDataTester(order=order, m_scalar_options=m_scalar_options, kronecker_factor=[1, 2],
                                               kronecker_sketch_sizes=katri_rao_sketch_sizes)
    kroncker_data_tester.run_kronecker_order_test_and_save()

    # Run TT Experiments
    ranks = [2 ** i for i in range(2, 6)] + [40, 50, 64, 70]
    m_scalar_options = [3, 4, 5, 6, 7, 8]
    tt_data_tester = TTDataTester(rank=ranks, m_scalar_options=m_scalar_options)
    tt_data_tester.run_rank_test_and_save()

    # Create Graphs
    AnalyzeResults.analyze_and_plot_tt_data(rank=ranks[-1])
    AnalyzeResults.analyze_and_plot_kroncker_data(order=order[-1])
    print("Saved graphs at:", "./results/graphs")