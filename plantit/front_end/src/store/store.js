import Vue from 'vue';
import Vuex from 'vuex';
import createPersistedState from 'vuex-persistedstate';
import axios from 'axios';
import Cookies from 'js-cookie';
import { user } from '@/store/user';
import { users } from '@/store/users';
import { workflows } from '@/store/workflows';
import { runs } from '@/store/runs';
import { notifications } from '@/store/notifications';

Vue.use(Vuex);

const store = new Vuex.Store({
    plugins: [
        createPersistedState({
            storage: window.sessionStorage
        })
    ],
    state: () => ({
        csrfToken: Cookies.get(axios.defaults.xsrfCookieName)
    }),
    getters: {
        csrfToken: state => state.csrfToken
    },
    modules: {
        user,
        users,
        workflows,
        runs,
        notifications
    }
});

export default store;
