import axios from 'axios';
import * as Sentry from '@sentry/browser';

export const users = {
    state: () => ({
        users: [],
        usersLoading: true
    }),
    mutations: {
        setUsers(state, users) {
            state.users = users;
        },
        setUsersLoading(state, loading) {
            state.usersLoading = loading;
        }
    },
    actions: {
        async loadUsers({ commit }) {
            commit('setUsersLoading', true);
            await axios
                .get('/apis/v1/users/')
                .then(response => {
                    commit('setUsers', response.data);
                    commit('setUsersLoading', false);
                })
                .catch(error => {
                    commit('setUsersLoading', false);
                    Sentry.captureException(error);
                    if (error.response.status === 500) throw error;
                });
        }
    },
    getters: {
        users: state => state.users,
        usersLoading: state => state.usersLoading
        // TODO add 'developers' (users who've contributed workflows)
    }
};
