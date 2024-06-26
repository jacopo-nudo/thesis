import pandas as pd
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import beta, burr
import powerlaw
import random
import math


def simulate_number_of_users(gamma_fb, min_users, size=1):
    # Simulate the number of users using a power-law distribution
    return min_users * (1 - np.random.rand(size))**(-1 / (gamma_fb - 1))

def simulate_initial_comment(a, b, loc, scale, size=1):
    # Simulate the initial comment using a Beta distribution
    return beta.rvs(a, b, loc, scale, size)

def simulate_number_of_comments(alpha, lambda_, size=1):
    # Simulate the inflated component (produces 0 with probability alpha)
    inflate = np.random.binomial(1, alpha, size)
    # Simulate the count component (negative exponential distribution)
    counts = np.random.exponential(1 / lambda_, size)
    # Discretize the exponential values to obtain integer count values
    counts = np.round(counts).astype(int)
    counts[counts < 0] = 0
    # Combine the inflated and count components
    simulated_data = inflate * counts
    return simulated_data

def simulate_data(social, parameters, num_threads=False, activate_tqdm=True, min_users=50):
    gamma=parameters['gamma']
    a=parameters['a']
    b=parameters['b']
    loc=parameters['loc']
    scale=parameters['scale']
    alpha=parameters['alpha']
    lambda_=parameters['lambda']
    c=parameters['c']
    d=parameters['d']
    l=parameters['l']
    s=parameters['s']
    cf=parameters['cf']
    df=parameters['df']
    lf=parameters['lf']
    sf=parameters['sf']
    ka=parameters['ka']
    kb=parameters['kb']
    kloc=parameters['kloc']
    kscale=parameters['kscale']
    data = []
    if num_threads:
        num_threads = min(num_threads, len(social['post_id'].unique()))
        thread_ids = random.sample(list(social['post_id'].unique()), num_threads)
    else:
        thread_ids = social['post_id'].unique()
    
    if activate_tqdm:
        thread_ids = tqdm(thread_ids)
    
    for th in thread_ids:
        thread = social[social['post_id'] == th]
        number_of_users = int(np.round(simulate_number_of_users(gamma, min_users, size=1)))
        T0s = simulate_initial_comment(a, b, loc, scale, size=number_of_users)

        for i in range(number_of_users):
            T0 = T0s[i]
            N = int(simulate_number_of_comments(alpha, lambda_)[0] + 1)
            if N > 1:
                additional_timings = burr.rvs(c, d, l, s, size=N-2)
                final_comment_additional_timings = burr.rvs(cf, df, lf, sf, size=1)
                timing = np.concatenate(([T0], additional_timings, final_comment_additional_timings))
            else:
                timing = np.array([T0])
            timing = np.cumsum(timing)
            timing = [x for x in timing if x <= 1]

            for j, t in enumerate(timing):
                data.append({'user_id': f'User_{i}', 'post_id': th, 'temporal_distance_birth_base_100h': t, 'sequential_number_of_comment_by_user_in_thread': j + 1})

    simulated = pd.DataFrame(data)
    observed = social[social['post_id'].isin(simulated['post_id'].unique())][['user_id', 'post_id', 'temporal_distance_birth_base_100h', 'sequential_number_of_comment_by_user_in_thread']]

    return simulated, observed

def calculate_ECDF(df, time_intervals, activate_tqdm=True):
    results_list = []
    df_c = df[df['sequential_number_of_comment_by_user_in_thread'] != 1]
    grouped = df.groupby('post_id')[['temporal_distance_birth_base_100h', 'sequential_number_of_comment_by_user_in_thread']]
    
    if activate_tqdm:
        grouped = tqdm(grouped, desc="Processing DataFrame")
    
    for post_id, group_data in grouped:
        results = pd.DataFrame(index=time_intervals)
        total_comments = len(group_data)
        
        for time in time_intervals:
            comments_within_time = np.sum(group_data['temporal_distance_birth_base_100h'] < time)
            comments_within_time_cc = np.sum(group_data[group_data['sequential_number_of_comment_by_user_in_thread'] != 1]['temporal_distance_birth_base_100h'] < time)
            
            share = comments_within_time / total_comments
            share_cc = comments_within_time_cc / total_comments
            
            results.at[time, 'Share'] = share
            results.at[time, 'Share_cc'] = share_cc
        
        results['post_id'] = post_id
        results = results.reset_index().rename(columns={'index': 'Time Grid Value'})
        results_list.append(results)
    
    final_results = pd.concat(results_list, ignore_index=True)

    return final_results

def plot_ECDF(df, level=95):
    plt.figure(figsize=(12, 8))
    sns.lineplot(data=df, x='Time Grid Value', y='Share', hue='Platform', err_style='band', errorbar=('ci', level))
    sns.lineplot(data=df, x='Time Grid Value', y='Share_cc', hue='Platform', err_style='band', errorbar=('ci', level), linestyle='dotted') 
    plt.title('Distribution of Conversation Lifetime Across Percentiles (Reddit vs Facebook)')
    plt.ylabel('Fraction of comments')
    plt.xlabel('Time (base 100)')
    plt.grid(False)
    plt.legend(title='Platform')
    plt.show()

def calculate_loss(observed, simulated):
    combined_results = pd.merge(observed, simulated, on=['post_id', 'Time Grid Value'], suffixes=('_Observed', '_Simulated'))
    combined_results['Errors'] = abs(combined_results['Share_Simulated'] - combined_results['Share_Observed']) + abs(combined_results['Share_cc_Simulated'] - combined_results['Share_cc_Observed'])
    total_error = combined_results['Errors'].sum()

    return total_error

def fit_power_law(data, xmin):
    fit = powerlaw.Fit(data, xmin=xmin, discrete=True)
    return fit.alpha

def fit_beta_distribution(data):
    data = data[data > 0]  # Filter out zero or negative values
    a, b, loc, scale = beta.fit(data)  # , floc=0, fscale=1)
    return {'a': a, 'b': b, 'loc': loc, 'scale': scale}

def simulate_data_M2(social, parameters, num_threads=False, activate_tqdm=True, min_users=50):
    gamma=parameters['gamma']
    a=parameters['a']
    b=parameters['b']
    loc=parameters['loc']
    scale=parameters['scale']
    alpha=parameters['alpha']
    lambda_=parameters['lambda']
    c=parameters['c']
    d=parameters['d']
    l=parameters['l']
    s=parameters['s']
    cf=parameters['cf']
    df=parameters['df']
    lf=parameters['lf']
    sf=parameters['sf']
    ka=parameters['ka']
    kb=parameters['kb']
    kloc=parameters['kloc']
    kscale=parameters['kscale']
    
    data = []
    if num_threads:
        num_threads = min(num_threads, len(social['post_id'].unique()))
        thread_ids = random.sample(list(social['post_id'].unique()), num_threads)
    else:
        thread_ids = social['post_id'].unique()
    
    if activate_tqdm:
        thread_ids = tqdm(thread_ids)

    for th in thread_ids:
        thread = social[social['post_id'] == th]
        number_of_users = int(np.round(simulate_number_of_users(gamma, min_users, size=1)[0]))
        T0s = simulate_initial_comment(a, b, loc, scale, size=number_of_users)
        Ns = simulate_number_of_comments(alpha, lambda_, number_of_users) + 1
        thread = [[T0s[i]] + [np.nan] * (Ns[i] - 1) for i in range(number_of_users)]
        thread = positioning_replies(thread, c, d, l, s, Ns, ka, kb, kloc, kscale)
        
        for u, interaction in enumerate(thread):
            timing = np.cumsum(np.array(interaction, dtype=float))
            timing = [x for x in timing if x <= 1]
            for j, t in enumerate(timing):
                data.append({'user_id': f'User_{u}', 'post_id': th, 'temporal_distance_birth_base_100h': t, 'sequential_number_of_comment_by_user_in_thread': j + 1})

    simulated = pd.DataFrame(data)
    observed = social[social['post_id'].isin(simulated['post_id'].unique())][['user_id', 'post_id', 'temporal_distance_birth_base_100h', 'sequential_number_of_comment_by_user_in_thread']]

    return simulated, observed

def positioning_replies(data, c, d, l, s, Ns, a, b, loc, scale):
    was_nan = []

    while True:
        candidates = []
        has_nan = False

        # Find all lists with nan and the last non-nan value
        for sublist in data:
            if math.isnan(sublist[-1]):
                non_nan_values = [x for x in sublist if not math.isnan(x)]
                if non_nan_values:
                    candidates.append((non_nan_values[-1], sublist))
                    has_nan = True

        # If there are no more candidates with nan, exit the loop
        if not has_nan:
            break

        candidates.sort(key=lambda x: x[0])
        most_recent_non_nan = candidates[0][0]
        target_list = candidates[0][1]
        all_values = sorted([x for sublist in data for x in sublist if not math.isnan(x)])
        index = all_values.index(most_recent_non_nan)

        k = beta.rvs(a, b, loc, scale, 1)[0]
        K = (k * sum(Ns)).astype(int)

        # Adjust K if it encounters a value that was originally NA
        adjusted_index = index
        for _ in range(K):
            adjusted_index += 1
            if adjusted_index < len(all_values) and all_values[adjusted_index] in was_nan:
                adjusted_index += 1

        if adjusted_index < len(all_values):
            new_value = all_values[adjusted_index]
        else:
            new_value = all_values[-1]

        for i in range(len(target_list)):
            if math.isnan(target_list[i]):
                iat = burr.rvs(c, d, l, s, size=1)
                if (new_value - sum(target_list[:i])) < 0.5*iat:
                    target_list[i] = iat[0]
                elif (new_value - sum(target_list[:i])) > 10 * iat:
                    target_list[i] = iat[0]
                else:
                    target_list[i] = new_value
                was_nan.append(target_list[i])
                break

    return data




